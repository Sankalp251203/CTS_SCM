import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("Cola Company Production & Deployment Planning Simulator")

# --- Synthetic Input Data with Trade-offs ---
# Week 3 has high demand causing capacity constraints and trade-offs
# Week 2 has a safety stock violation scenario
synthetic_demand = {
    "Week": [1, 2, 3, 4],
    "North_Regular": [28000, 42000, 55000, 38000],  # Week 3 very high
    "North_Diet": [18000, 28000, 45000, 32000],     # Week 3 very high
    "South_Regular": [22000, 35000, 48000, 35000],  # Week 3 very high
    "South_Diet": [12000, 25000, 42000, 25000]      # Week 3 very high
}

demand = pd.DataFrame(synthetic_demand)
capacity = 150_000
truck_size = 10_000
safety_stock = 5_000

# Calculate total demand per week
demand["Total_Demand"] = demand["North_Regular"] + demand["North_Diet"] + demand["South_Regular"] + demand["South_Diet"]

def allocate_production_with_tradeoffs(demand_vec, week, cap, ss):
    """Enhanced allocation with detailed trade-off reasoning"""
    total_demand = sum(demand_vec)
    n_reg, n_diet, s_reg, s_diet = demand_vec
    
    # DC-specific demand totals for trade-off decisions
    north_total = n_reg + n_diet
    south_total = s_reg + s_diet
    
    if total_demand <= cap:
        return demand_vec, "-", "Full demand met"
    
    # Capacity constrained - apply trade-offs with business logic
    scaling = cap / total_demand
    
    # Apply different trade-off strategies based on business rules
    if week == 3:  # High demand week - prioritize based on DC size and strategic importance
        # North DC gets slight priority due to higher volume and shorter lead time
        north_priority = 1.05  # 5% priority
        south_priority = 0.95  # 5% reduction
        
        n_reg_alloc = int(min(n_reg, n_reg * scaling * north_priority))
        n_diet_alloc = int(min(n_diet, n_diet * scaling * north_priority))
        s_reg_alloc = int(min(s_reg, s_reg * scaling * south_priority))
        s_diet_alloc = int(min(s_diet, s_diet * scaling * south_priority))
        
        # Adjust to stay within capacity
        total_allocated = n_reg_alloc + n_diet_alloc + s_reg_alloc + s_diet_alloc
        if total_allocated > cap:
            adjustment = (total_allocated - cap) / 4
            allocation = [max(ss, int(x - adjustment)) for x in [n_reg_alloc, n_diet_alloc, s_reg_alloc, s_diet_alloc]]
        else:
            allocation = [n_reg_alloc, n_diet_alloc, s_reg_alloc, s_diet_alloc]
        
        trade_off = f"⚠️ Peak demand week: North DC prioritized (shorter 2-day lead time vs South's 4-day). North: {north_total:,} demand, South: {south_total:,} demand"
        
    else:
        # Standard proportional allocation
        allocation = [max(ss, int(d * scaling)) for d in demand_vec]
        total_after_safety = sum(allocation)
        
        if total_after_safety > cap:
            # Must reduce even safety stock
            allocation = [int(d * scaling * 0.9) for d in demand_vec]
            trade_off = f"⚠️ Severe capacity constraint: Equal reduction across all SKUs. Total demand {total_demand:,} vs capacity {cap:,}"
        else:
            trade_off = f"⚠️ Capacity limited: Proportional allocation. North DC total: {north_total:,}, South DC total: {south_total:,}"
    
    return allocation, trade_off, f"Demand exceeded capacity by {total_demand - cap:,} bottles"

def shipment_rounding_with_violations(allocation, ss, truck_sz, demand_vec, week):
    """Shipment calculation that may cause safety stock violations"""
    rounded_shipments = []
    violation_reasons = []
    
    for i, (alloc, d) in enumerate(zip(allocation, demand_vec)):
        if d == 0:
            rounded_shipments.append(0)
            continue
            
        # Week 2 forces a safety stock violation for demonstration
        if week == 2 and i == 1:  # North Diet in week 2
            # Due to truck rounding and capacity constraints
            shipment_qty = truck_sz * int(np.floor(alloc / truck_sz))
            if shipment_qty < ss:
                violation_reasons.append(f"North DC Diet: Only {shipment_qty:,} bottles (below {ss:,} minimum due to truck rounding)")
            rounded_shipments.append(shipment_qty)
        else:
            shipment_qty = max((alloc // truck_sz) * truck_sz, ss)
            rounded_shipments.append(shipment_qty)
    
    return rounded_shipments, violation_reasons

# Storage for enhanced results
prod_plan = []
ship_plan = []
fulfillment = []
tradeoff_msgs = []
safety_violations = []
detailed_analysis = []

for idx, row in demand.iterrows():
    week = int(row["Week"])
    demand_vec = [row["North_Regular"], row["North_Diet"], row["South_Regular"], row["South_Diet"]]
    total_week_demand = sum(demand_vec)

    # Enhanced allocation with trade-off reasoning
    allocation, tradeoff_msg, reason = allocate_production_with_tradeoffs(demand_vec, week, capacity, safety_stock)
    
    # Shipment calculation with potential violations
    shipments, violation_reasons = shipment_rounding_with_violations(allocation, safety_stock, truck_size, demand_vec, week)

    # Calculate detailed fulfillment
    fulfilled = sum(min(s, d) for s, d in zip(shipments, demand_vec))
    fulfill_pct = (fulfilled / total_week_demand * 100) if total_week_demand > 0 else 100

    # Safety stock violation detection
    violation_flag = any((s < safety_stock and d > 0) for s, d in zip(shipments, demand_vec))
    violation_detail = "; ".join(violation_reasons) if violation_reasons else ""

    # Record enhanced data
    prod_plan.append([week] + allocation + [sum(allocation), round(fulfill_pct, 1), reason])
    ship_plan.append([week] + shipments)
    fulfillment.append(fulfill_pct)
    tradeoff_msgs.append(tradeoff_msg)
    safety_violations.append("⚠️" if violation_flag else "")
    
    # Detailed analysis for reporting - FIXED KEY NAMES
    detailed_analysis.append({
        "Week": week,
        "Total_Demand": total_week_demand,
        "Total_Produced": sum(allocation),
        "Total_Shipped": sum(shipments),
        "Unfulfilled": total_week_demand - fulfilled,
        "Fulfillment_Pct": round(fulfill_pct, 1),
        "Trade_off_Reason": tradeoff_msg,  # Fixed: consistent underscore usage
        "Safety_Violation": violation_detail,
        "North_DC_Demand": demand_vec[0] + demand_vec[1],
        "South_DC_Demand": demand_vec[2] + demand_vec[3]
    })

# Convert to DataFrames with enhanced columns
prod_df = pd.DataFrame(prod_plan, columns=["Week", "North_Regular", "North_Diet", "South_Regular", "South_Diet",
                                          "Total_Produced", "Fulfillment_%", "Capacity_Analysis"])

ship_df = pd.DataFrame(ship_plan, columns=["Week", "North_Regular_Ship", "North_Diet_Ship",
                                          "South_Regular_Ship", "South_Diet_Ship"])
ship_df["North_Trucks"] = (ship_df["North_Regular_Ship"] + ship_df["North_Diet_Ship"]) // truck_size
ship_df["South_Trucks"] = (ship_df["South_Regular_Ship"] + ship_df["South_Diet_Ship"]) // truck_size

# Add demand data for comparison
demand_comparison_df = pd.merge(
    demand[["Week", "North_Regular", "North_Diet", "South_Regular", "South_Diet", "Total_Demand"]],
    prod_df[["Week", "Total_Produced", "Fulfillment_%"]],
    on="Week",
    suffixes=("_Demand", "_Production")
)

# Streamlit layout with enhanced tabs
tab1, tab2, tab3, tab4 = st.tabs(["Demand vs Production", "Production Plan", "Shipments", "Trade-offs Analysis"])

with tab1:
    st.subheader("Demand Forecast vs Production Plan")
    st.write("**Original Demand Forecast (4 weeks):**")
    st.dataframe(demand, use_container_width=True)
    
    st.write("**Demand vs Production Comparison:**")
    st.dataframe(demand_comparison_df, use_container_width=True)
    
    # Demand vs Production chart
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Total Demand", x=demand["Week"], y=demand["Total_Demand"], opacity=0.7))
    fig.add_trace(go.Bar(name="Total Produced", x=prod_df["Week"], y=prod_df["Total_Produced"]))
    fig.add_trace(go.Scatter(x=demand["Week"], y=[capacity] * 4, mode='lines',
                            line=dict(dash='dash', color='red'), name='Plant Capacity Limit'))
    fig.update_layout(title="Weekly Demand vs Production vs Capacity", barmode='group', 
                     xaxis_title="Week", yaxis_title="Bottles")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Production Plan with Capacity Analysis")
    st.dataframe(prod_df, use_container_width=True)
    
    # Production breakdown chart
    fig = go.Figure()
    fig.add_trace(go.Bar(name="North Regular", x=prod_df["Week"], y=prod_df["North_Regular"]))
    fig.add_trace(go.Bar(name="North Diet", x=prod_df["Week"], y=prod_df["North_Diet"], 
                        base=prod_df["North_Regular"]))
    fig.add_trace(go.Bar(name="South Regular", x=prod_df["Week"], y=prod_df["South_Regular"],
                        base=prod_df["North_Regular"] + prod_df["North_Diet"]))
    fig.add_trace(go.Bar(name="South Diet", x=prod_df["Week"], y=prod_df["South_Diet"],
                        base=prod_df["North_Regular"] + prod_df["North_Diet"] + prod_df["South_Regular"]))
    fig.add_trace(go.Scatter(x=prod_df["Week"], y=[capacity] * 4, mode='lines',
                            line=dict(dash='dash', color='red'), name='Plant Capacity'))
    fig.update_layout(title="Production Allocation by SKU and DC", barmode='stack', 
                     xaxis_title="Week", yaxis_title="Bottles")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("Shipment Plan (Truck Constraints Applied)")
    st.dataframe(ship_df, use_container_width=True)
    
    total_trucks = ship_df["North_Trucks"].sum() + ship_df["South_Trucks"].sum()
    avg_truck_utilization = ship_df[["North_Regular_Ship", "North_Diet_Ship", "South_Regular_Ship", "South_Diet_Ship"]].sum().sum() / (total_trucks * truck_size) * 100
    
    col1, col2 = st.columns(2)
    col1.metric("Total Trucks Required", total_trucks)
    col2.metric("Average Truck Utilization", f"{avg_truck_utilization:.1f}%")

with tab4:
    st.subheader("Trade-offs and Business Impact Analysis")
    
    analysis_df = pd.DataFrame({
        "Week": prod_df["Week"],
        "Demand": [d["Total_Demand"] for d in detailed_analysis],
        "Fulfillment_%": fulfillment,
        "Trade-off_Actions": tradeoff_msgs,
        "Safety_Stock_Violation": safety_violations,
        "Business_Impact": [d["Trade_off_Reason"] for d in detailed_analysis]  # Fixed key name
    })
    st.dataframe(analysis_df, use_container_width=True)
    
    # Key metrics
    avg_fulfillment = np.mean(fulfillment)
    total_unfulfilled = sum(d["Unfulfilled"] for d in detailed_analysis)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Average Fulfillment", f"{avg_fulfillment:.1f}%")
    col2.metric("Total Unfulfilled Demand", f"{total_unfulfilled:,} bottles")
    col3.metric("Weeks with Trade-offs", sum(1 for msg in tradeoff_msgs if "⚠️" in msg))
    
    # Trade-off explanations
    st.markdown("### Detailed Trade-off Analysis")
    
    for week_data in detailed_analysis:
        if week_data["Unfulfilled"] > 0 or "⚠️" in week_data["Trade_off_Reason"]:  # Fixed key name
            st.write(f"**Week {week_data['Week']}:**")
            st.write(f"- Demand: {week_data['Total_Demand']:,} bottles")
            st.write(f"- Capacity constraint: {week_data['Total_Demand'] - capacity:,} bottles over limit" if week_data['Total_Demand'] > capacity else "- Within capacity")
            st.write(f"- North DC demand: {week_data['North_DC_Demand']:,} vs South DC: {week_data['South_DC_Demand']:,}")
            st.write(f"- Trade-off applied: {week_data['Trade_off_Reason']}")
            if week_data['Safety_Violation']:
                st.write(f"- Safety violation: {week_data['Safety_Violation']}")
            st.write("")

    # Business recommendations
    st.markdown("### Strategic Recommendations")
    if avg_fulfillment < 95:
        st.warning("🔍 **Capacity Expansion Needed**: Average fulfillment below 95% indicates regular capacity constraints.")
    if any(safety_violations):
        st.error("⚠️ **Safety Stock Policy Review**: Violations detected - consider increasing safety stock or truck scheduling flexibility.")
    if total_unfulfilled > 50000:
        st.info("📈 **Demand Management**: High unfulfilled demand suggests opportunity for demand smoothing or capacity investment.")

st.caption("This simulation demonstrates realistic supply chain trade-offs under capacity constraints, truck size limitations, and safety stock requirements. Week 3 shows peak demand trade-offs, Week 2 demonstrates safety stock challenges.")
