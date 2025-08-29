import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("Cola Company Production & Deployment Planning Simulator")

# --- Synthetic Input Data with Trade-offs ---
synthetic_demand = {
    "Week": [1, 2, 3, 4],
    "North_Regular": [28000, 42000, 55000, 38000],
    "North_Diet": [18000, 28000, 45000, 32000],
    "South_Regular": [22000, 35000, 48000, 35000],
    "South_Diet": [12000, 25000, 42000, 25000]
}
demand = pd.DataFrame(synthetic_demand)

# Constraints
capacity = 150_000
truck_size = 10_000
safety_stock = 5_000

# Total demand
demand["Total_Demand"] = demand[["North_Regular","North_Diet","South_Regular","South_Diet"]].sum(axis=1)

def allocate_production_with_tradeoffs(demand_vec, week, cap, ss):
    total_demand = sum(demand_vec)
    n_reg, n_diet, s_reg, s_diet = demand_vec
    north_total = n_reg + n_diet
    south_total = s_reg + s_diet

    if total_demand <= cap:
        return demand_vec, "-", "Full demand met"

    scaling = cap / total_demand

    if week == 3:
        north_priority = 1.05
        south_priority = 0.95
        n_reg_alloc = int(min(n_reg, n_reg * scaling * north_priority))
        n_diet_alloc = int(min(n_diet, n_diet * scaling * north_priority))
        s_reg_alloc = int(min(s_reg, s_reg * scaling * south_priority))
        s_diet_alloc = int(min(s_diet, s_diet * scaling * south_priority))
        total_allocated = n_reg_alloc + n_diet_alloc + s_reg_alloc + s_diet_alloc
        if total_allocated > cap:
            adjustment = (total_allocated - cap) / 4
            allocation = [max(ss, int(x - adjustment)) for x in [n_reg_alloc, n_diet_alloc, s_reg_alloc, s_diet_alloc]]
        else:
            allocation = [n_reg_alloc, n_diet_alloc, s_reg_alloc, s_diet_alloc]
        trade_off = f"⚠️ Peak demand week: North DC prioritized (shorter 2-day lead time vs South's 4-day). North: {north_total:,} demand, South: {south_total:,} demand"
    else:
        allocation = [max(ss, int(d * scaling)) for d in demand_vec]
        total_after_safety = sum(allocation)
        if total_after_safety > cap:
            allocation = [int(d * scaling * 0.9) for d in demand_vec]
            trade_off = f"⚠️ Severe capacity constraint: Equal reduction across all SKUs. Total demand {total_demand:,} vs capacity {cap:,}"
        else:
            trade_off = f"⚠️ Capacity limited: Proportional allocation. North DC total: {north_total:,}, South DC total: {south_total:,}"

    return allocation, trade_off, f"Demand exceeded capacity by {total_demand - cap:,} bottles"

def shipment_rounding_with_violations(allocation, ss, truck_sz, demand_vec, week):
    rounded_shipments = []
    violation_reasons = []
    for i, (alloc, d) in enumerate(zip(allocation, demand_vec)):
        if d == 0:
            rounded_shipments.append(0)
            continue
        # Week 2 demo: let rounding create a possible violation
        if week == 2 and i == 1:
            shipment_qty = truck_sz * int(np.floor(alloc / truck_sz))
            if shipment_qty < ss:
                violation_reasons.append(f"North DC Diet: Only {shipment_qty:,} bottles (below {ss:,} minimum due to truck rounding)")
            rounded_shipments.append(shipment_qty)
        else:
            shipment_qty = max((alloc // truck_sz) * truck_sz, ss)
            rounded_shipments.append(shipment_qty)
    return rounded_shipments, violation_reasons

# Accumulators
prod_plan, ship_plan = [], []
fulfillment, tradeoff_msgs, safety_violations = [], [], []
detailed_analysis = []

for _, row in demand.iterrows():
    week = int(row["Week"])
    demand_vec = [row["North_Regular"], row["North_Diet"], row["South_Regular"], row["South_Diet"]]
    total_week_demand = sum(demand_vec)

    allocation, tradeoff_msg, reason = allocate_production_with_tradeoffs(demand_vec, week, capacity, safety_stock)
    shipments, violation_reasons = shipment_rounding_with_violations(allocation, safety_stock, truck_size, demand_vec, week)

    fulfilled = sum(min(s, d) for s, d in zip(shipments, demand_vec))
    fulfill_pct = (fulfilled / total_week_demand * 100) if total_week_demand > 0 else 100

    violation_flag = any((s < safety_stock and d > 0) for s, d in zip(shipments, demand_vec))
    violation_detail = "; ".join(violation_reasons) if violation_reasons else ""

    prod_plan.append([week] + allocation + [sum(allocation), round(fulfill_pct, 1), reason])
    ship_plan.append([week] + shipments)
    fulfillment.append(fulfill_pct)
    tradeoff_msgs.append(tradeoff_msg)
    safety_violations.append("⚠️" if violation_flag else "")

    detailed_analysis.append({
        "Week": week,
        "Total_Demand": total_week_demand,
        "Total_Produced": sum(allocation),
        "Total_Shipped": sum(shipments),
        "Unfulfilled": total_week_demand - fulfilled,
        "Fulfillment_Pct": round(fulfill_pct, 1),
        "Trade_off_Reason": tradeoff_msg,  # consistent key
        "Safety_Violation": violation_detail,
        "North_DC_Demand": demand_vec + demand_vec[1],
        "South_DC_Demand": demand_vec[2] + demand_vec[3]
    })

# DataFrames
prod_df = pd.DataFrame(
    prod_plan,
    columns=["Week","North_Regular","North_Diet","South_Regular","South_Diet","Total_Produced","Fulfillment_%","Capacity_Analysis"]
)
ship_df = pd.DataFrame(
    ship_plan,
    columns=["Week","North_Regular_Ship","North_Diet_Ship","South_Regular_Ship","South_Diet_Ship"]
)

# Use ceil to avoid undercounting trucks
ship_df["North_Trucks"] = np.ceil((ship_df["North_Regular_Ship"] + ship_df["North_Diet_Ship"]) / truck_size).astype(int)
ship_df["South_Trucks"] = np.ceil((ship_df["South_Regular_Ship"] + ship_df["South_Diet_Ship"]) / truck_size).astype(int)

# Comparison
demand_comparison_df = pd.merge(
    demand[["Week","North_Regular","North_Diet","South_Regular","South_Diet","Total_Demand"]],
    prod_df[["Week","Total_Produced","Fulfillment_%"]],
    on="Week"
)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Demand vs Production", "Production Plan", "Shipments", "Trade-offs Analysis"])

with tab1:
    st.subheader("Demand Forecast vs Production Plan")
    st.dataframe(demand, use_container_width=True)

    st.write("**Demand vs Production Comparison:**")
    st.dataframe(demand_comparison_df, use_container_width=True)

    # --- Trade-off Trends (Weekly) ---
    st.subheader("Trade-off Trends by Week (Forecast + Annotations)")

    trend_df = pd.DataFrame(detailed_analysis)

    # Flags and severity index (use correct key name and guard NaN)
    trend_df["Capacity_Shortfall"] = (trend_df["Total_Demand"] - capacity).clip(lower=0).astype(int)
    trend_df["Safety_Flag"] = trend_df["Safety_Violation"].fillna("").str.len().gt(0).astype(int)
    trend_df["Tradeoff_Flag"] = trend_df["Trade_off_Reason"].fillna("").str.contains("⚠️").astype(int)

    trend_df["Severity_Index"] = (trend_df["Capacity_Shortfall"] / capacity).round(3) + 0.5 * trend_df["Safety_Flag"]

    trend_df["Tradeoff_Annotation"] = np.where(
        trend_df["Tradeoff_Flag"].eq(1),
        trend_df["Trade_off_Reason"].fillna("").str.replace("⚠️ ", "", regex=False).str.slice(0, 40) + "...",
        "No trade-off"
    )

    st.dataframe(
        trend_df[["Week","Total_Demand","Total_Produced","Capacity_Shortfall","Safety_Flag","Severity_Index","Trade_off_Reason"]],
        use_container_width=True
    )

    # Forecast & trade-off trend line chart
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=trend_df["Week"], y=trend_df["Total_Demand"], mode="lines+markers",
                                   name="Forecast Demand", line=dict(width=3, color="#1f77b4")))
    fig_trend.add_trace(go.Scatter(x=trend_df["Week"], y=trend_df["Total_Produced"], mode="lines+markers",
                                   name="Planned Production", line=dict(width=3, color="#2ca02c")))
    fig_trend.add_trace(go.Scatter(x=trend_df["Week"], y=(trend_df["Severity_Index"]*capacity),
                                   mode="lines+markers", name="Trade-off Severity (scaled)",
                                   line=dict(width=2, dash="dot", color="#d62728")))
    fig_trend.add_hline(y=capacity, line_width=2, line_dash="dash", line_color="red",
                        annotation_text="Plant Capacity", annotation_position="top right")
    fig_trend.add_trace(go.Scatter(x=trend_df["Week"], y=trend_df["Total_Demand"], mode="markers+text",
                                   text=trend_df["Tradeoff_Annotation"], textposition="top center",
                                   name="Trade-off Notes", marker=dict(size=1, color="rgba(0,0,0,0)")))
    fig_trend.update_layout(title="Weekly Forecast vs Production with Trade-off Trends",
                            xaxis_title="Week", yaxis_title="Bottles", hovermode="x unified")
    st.plotly_chart(fig_trend, use_container_width=True)

    # Demand vs Production bar chart
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Total Demand", x=demand["Week"], y=demand["Total_Demand"], opacity=0.7))
    fig.add_trace(go.Bar(name="Total Produced", x=prod_df["Week"], y=prod_df["Total_Produced"]))
    fig.add_trace(go.Scatter(x=demand["Week"], y=[capacity]*len(demand), mode="lines",
                             line=dict(dash='dash', color='red'), name='Plant Capacity Limit'))
    fig.update_layout(title="Weekly Demand vs Production vs Capacity", barmode='group',
                      xaxis_title="Week", yaxis_title="Bottles")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Production Plan with Capacity Analysis")
    st.dataframe(prod_df, use_container_width=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="North Regular", x=prod_df["Week"], y=prod_df["North_Regular"]))
    fig.add_trace(go.Bar(name="North Diet", x=prod_df["Week"], y=prod_df["North_Diet"], base=prod_df["North_Regular"]))
    fig.add_trace(go.Bar(name="South Regular", x=prod_df["Week"], y=prod_df["South_Regular"],
                         base=prod_df["North_Regular"]+prod_df["North_Diet"]))
    fig.add_trace(go.Bar(name="South Diet", x=prod_df["Week"], y=prod_df["South_Diet"],
                         base=prod_df["North_Regular"]+prod_df["North_Diet"]+prod_df["South_Regular"]))
    fig.add_trace(go.Scatter(x=prod_df["Week"], y=[capacity]*len(prod_df), mode='lines',
                             line=dict(dash='dash', color='red'), name='Plant Capacity'))
    fig.update_layout(title="Production Allocation by SKU and DC", barmode='stack',
                      xaxis_title="Week", yaxis_title="Bottles")
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("Shipment Plan (Truck Constraints Applied)")
    st.dataframe(ship_df, use_container_width=True)
    total_trucks = ship_df["North_Trucks"].sum() + ship_df["South_Trucks"].sum()
    total_bottles_shipped = ship_df[["North_Regular_Ship","North_Diet_Ship","South_Regular_Ship","South_Diet_Ship"]].sum().sum()
    avg_truck_utilization = (total_bottles_shipped / (total_trucks * truck_size) * 100) if total_trucks > 0 else 0
    col1, col2 = st.columns(2)
    col1.metric("Total Trucks Required", int(total_trucks))
    col2.metric("Average Truck Utilization", f"{avg_truck_utilization:.1f}%")

with tab4:
    st.subheader("Trade-offs and Business Impact Analysis")
    analysis_df = pd.DataFrame({
        "Week": prod_df["Week"],
        "Demand": [d["Total_Demand"] for d in detailed_analysis],
        "Fulfillment_%": fulfillment,
        "Trade-off_Actions": tradeoff_msgs,
        "Safety_Stock_Violation": safety_violations,
        "Business_Impact": [d["Trade_off_Reason"] for d in detailed_analysis]
    })
    st.dataframe(analysis_df, use_container_width=True)

    avg_fulfillment = float(np.mean(fulfillment)) if fulfillment else 100.0
    total_unfulfilled = int(sum(d["Unfulfilled"] for d in detailed_analysis))
    col1, col2, col3 = st.columns(3)
    col1.metric("Average Fulfillment", f"{avg_fulfillment:.1f}%")
    col2.metric("Total Unfulfilled Demand", f"{total_unfulfilled:,} bottles")
    col3.metric("Weeks with Trade-offs", sum(1 for msg in tradeoff_msgs if "⚠️" in msg))

    st.markdown("### Detailed Trade-off Analysis")
    for week_data in detailed_analysis:
        if week_data["Unfulfilled"] > 0 or "⚠️" in week_data["Trade_off_Reason"]:
            st.write(f"**Week {week_data['Week']}:**")
            st.write(f"- Demand: {week_data['Total_Demand']:,} bottles")
            st.write(f"- Capacity constraint: {max(0, week_data['Total_Demand'] - capacity):,} bottles over limit"
                     if week_data['Total_Demand'] > capacity else "- Within capacity")
            st.write(f"- North DC demand: {week_data['North_DC_Demand']:,} vs South DC: {week_data['South_DC_Demand']:,}")
            st.write(f"- Trade-off applied: {week_data['Trade_off_Reason']}")
            if week_data['Safety_Violation']:
                st.write(f"- Safety violation: {week_data['Safety_Violation']}")
            st.write("")

    st.markdown("### Strategic Recommendations")
    if avg_fulfillment < 95:
        st.warning("🔍 Capacity expansion or smoothing may be needed.")
    if any(safety_violations):
        st.error("⚠️ Safety stock violations detected—review floor levels or routing.")
    if total_unfulfilled > 50_000:
        st.info("📈 Consider demand shaping or incremental capacity during peaks.")

st.caption("This simulation demonstrates realistic trade-offs under capacity, truck size, and safety stock constraints with weekly demand forecasts and annotated trends.")
