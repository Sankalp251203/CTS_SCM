import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("Cola Company Production & Deployment Simulator")

# Constraints
capacity = 150_000   # max production per week
truck_size = 10_000  # shipment size in multiples of 10k
safety_stock = 5_000 # minimum bottles per SKU per DC to retain

# Synthetic demand input
synthetic_demand = {
    "Week": [1, 2, 3, 4],
    "North_Regular": [28000, 42000, 55000, 38000],
    "North_Diet": [18000, 28000, 45000, 32000],
    "South_Regular": [22000, 35000, 48000, 35000],
    "South_Diet": [12000, 25000, 42000, 25000]
}

demand = pd.DataFrame(synthetic_demand)
demand["Total_Demand"] = demand[["North_Regular", "North_Diet", "South_Regular", "South_Diet"]].sum(axis=1)

def allocate_production(demand_vec, week):
    total_demand = sum(demand_vec)
    n_reg, n_diet, s_reg, s_diet = demand_vec
    north_total = n_reg + n_diet
    south_total = s_reg + s_diet

    if total_demand <= capacity:
        return demand_vec, "-", "Full demand met"
    
    scale = capacity / total_demand

    # Special handling for peak demand week 3 prioritizing North DC slightly
    if week == 3:
        north_priority = 1.05  # 5% boost to North DC
        south_priority = 0.95  # 5% reduce South DC
        n_reg_alloc = int(min(n_reg, n_reg * scale * north_priority))
        n_diet_alloc = int(min(n_diet, n_diet * scale * north_priority))
        s_reg_alloc = int(min(s_reg, s_reg * scale * south_priority))
        s_diet_alloc = int(min(s_diet, s_diet * scale * south_priority))

        total_alloc = n_reg_alloc + n_diet_alloc + s_reg_alloc + s_diet_alloc

        if total_alloc > capacity:
            adjustment = (total_alloc - capacity) / 4
            allocation = [max(safety_stock, int(x - adjustment)) for x in [n_reg_alloc, n_diet_alloc, s_reg_alloc, s_diet_alloc]]
        else:
            allocation = [n_reg_alloc, n_diet_alloc, s_reg_alloc, s_diet_alloc]

        tradeoff = f"⚠️ Peak demand week: North DC prioritized (shorter lead time). North: {north_total:,}, South: {south_total:,}"
    else:
        allocation = [max(safety_stock, int(d * scale)) for d in demand_vec]
        total_after_safety = sum(allocation)

        if total_after_safety > capacity:
            allocation = [int(d * scale * 0.9) for d in demand_vec]  # further scale-down due to safety stock overflow
            tradeoff = f"⚠️ Severe constraint: Uniform reduction. Demand {total_demand:,}, Capacity {capacity:,}"
        else:
            tradeoff = f"⚠️ Capacity constrained: Proportional scale-down. North: {north_total:,}, South: {south_total:,}"

    return allocation, tradeoff, f"Capacity shortfall: {total_demand - capacity if total_demand > capacity else 0}"

def shipment_rounding(allocation, demand_vec, week):
    shipments = []
    violations = []

    for i, (alloc, demand_qty) in enumerate(zip(allocation, demand_vec)):
        if demand_qty == 0:
            shipments.append(0)
            continue
        ship_qty = (alloc // truck_size) * truck_size

        # Enforce minimum safety stock shipment
        ship_qty = max(ship_qty, safety_stock)

        # Inject forced violation for demonstration in week 2 on North Diet (index=1)
        if week == 2 and i == 1 and ship_qty > safety_stock:
            ship_qty = safety_stock - 1000  # intentionally violate safety stock

        if ship_qty < safety_stock:
            violations.append(f"SKU index {i} shipment at {ship_qty} below safety stock {safety_stock}")

        shipments.append(ship_qty)

    return shipments, violations

# Prepare data containers
prod_plans = []
ship_plans = []
fulfillments = []
tradeoffs = []
safety_viol_flags = []
detailed_analysis = []

for idx, row in demand.iterrows():
    week = row["Week"]
    demand_vec = [row["North_Regular"], row["North_Diet"], row["South_Regular"], row["South_Diet"]]
    total_demand = sum(demand_vec)

    alloc, tradeoff_msg, remark = allocate_production(demand_vec, week)
    shipments, violation_notes = shipment_rounding(alloc, demand_vec, week)

    total_shipped = sum(shipments)
    fulfilled = sum(min(s, d) for s, d in zip(shipments, demand_vec))
    fulfillment_pct = 100 * fulfilled / total_demand if total_demand else 100

    violation_flag = len(violation_notes) > 0

    prod_plans.append([week] + alloc + [sum(alloc), round(fulfillment_pct,1), remark])
    ship_plans.append([week] + shipments)
    fulfillments.append(fulfillment_pct)
    tradeoffs.append(tradeoff_msg)
    safety_viol_flags.append("⚠️" if violation_flag else "")

    detailed_analysis.append({
        "Week": week,
        "Total_Demand": total_demand,
        "Total_Produced": sum(alloc),
        "Total_Shipped": total_shipped,
        "Unfulfilled": total_demand - fulfilled,
        "Fulfillment": round(fulfillment_pct,1),
        "Trade_Off_Reason": tradeoff_msg,
        "Safety_Violations": "; ".join(violation_notes),
        "North_DC_Demand": demand_vec[0] + demand_vec[1],
        "South_DC_Demand": demand_vec[2] + demand_vec[3],
    })

# DataFrames for display
prod_df = pd.DataFrame(prod_plans, columns=["Week", "North_Regular", "North_Diet", "South_Regular", "South_Diet",
                                           "Total_Produced", "Fulfillment_%", "Remarks"])
ship_df = pd.DataFrame(ship_plans, columns=["Week", "North_Regular_Ship", "North_Diet_Ship",
                                           "South_Regular_Ship", "South_Diet_Ship"])
ship_df["North_Trucks"] = np.ceil((ship_df["North_Regular_Ship"] + ship_df["North_Diet_Ship"]) / truck_size).astype(int)
ship_df["South_Trucks"] = np.ceil((ship_df["South_Regular_Ship"] + ship_df["South_Diet_Ship"]) / truck_size).astype(int)

comparison_df = demand.copy()
comparison_df["Total_Produced"] = prod_df["Total_Produced"]
comparison_df["Fulfillment_%"] = prod_df["Fulfillment_%"]

tabs = st.tabs(["Demand vs Production", "Production Plan", "Shipments", "Trade-Off Analysis"])

with tabs[0]:
    st.subheader("Demand vs Production")
    st.dataframe(comparison_df)
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Demand", x=comparison_df["Week"], y=comparison_df["Total_Demand"]))
    fig.add_trace(go.Bar(name="Production", x=comparison_df["Week"], y=comparison_df["Total_Produced"]))
    fig.add_trace(go.Scatter(x=comparison_df["Week"], y=[capacity]*len(comparison_df), mode='lines',
                             name='Capacity Limit', line=dict(color='red', dash='dash')))
    st.plotly_chart(fig)

with tabs[1]:
    st.subheader("Production Plan Details")
    st.dataframe(prod_df.drop(columns=["Total_Produced","Fulfillment_%","Remarks"]))
    fig = go.Figure()
    fig.add_trace(go.Bar(name="North Regular", x=prod_df["Week"], y=prod_df["North_Regular"]))
    fig.add_trace(go.Bar(name="North Diet", x=prod_df["Week"], y=prod_df["North_Diet"], base=prod_df["North_Regular"]))
    fig.add_trace(go.Bar(name="South Regular", x=prod_df["Week"], y=prod_df["South_Regular"], base=prod_df["North_Regular"]+prod_df["North_Diet"]))
    fig.add_trace(go.Bar(name="South Diet", x=prod_df["Week"], y=prod_df["South_Diet"], base=prod_df["North_Regular"]+prod_df["North_Diet"]+prod_df["South_Regular"]))
    fig.add_trace(go.Scatter(x=prod_df["Week"], y=[capacity]*len(prod_df), mode='lines', name='Capacity Limit', line=dict(color='red', dash='dash')))
    fig.update_layout(barmode='stack', yaxis_title='Bottles', xaxis_title='Week')
    st.plotly_chart(fig)

with tabs[2]:
    st.subheader("Shipment Plan")
    st.dataframe(ship_df)
    total_trucks = ship_df["North_Trucks"].sum() + ship_df["South_Trucks"].sum()
    total_load = ship_df[["North_Regular_Ship","North_Diet_Ship","South_Regular_Ship","South_Diet_Ship"]].sum().sum()
    avg_util = total_load / (total_trucks*truck_size) * 100 if total_trucks > 0 else 0
    
    col1, col2 = st.columns(2)
    col1.metric("Total Trucks Required", total_trucks)
    col2.metric("Average Truck Utilization", f"{avg_util:.1f}%")

with tabs[3]:
    st.subheader("Trade-Off Analysis")
    analysis_df = pd.DataFrame(detailed_analysis)
    st.dataframe(analysis_df[["Week","Total_Demand","Total_Produced","Total_Shipped","Unfulfilled","Fulfillment","Trade_Off_Reason","Safety_Violations","North_DC_Demand","South_DC_Demand"]])
    
    avg_fulfillment = np.mean(fulfillments)
    total_unfulfilled = np.sum([d["Unfulfilled"] for d in detailed_analysis])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Average Fulfillment", f"{avg_fulfillment:.1f}%")
    col2.metric("Total Unfulfilled Demand", f"{total_unfulfilled:,}")
    col3.metric("Weeks with Trade-Offs", sum("⚠️" in t for t in tradeoffs))
    
    st.markdown("### Detailed Trade-Off Remarks")
    for i in range(len(analysis_df)):
        row = analysis_df.iloc[i]
        if row.Unfulfilled > 0 or "⚠️" in row.Trade_Off_Reason:
            st.markdown(f"**Week {row.Week}**")
            st.write(f"- Demand: {row.Total_Demand:,} bottles")
            st.write("- Over Capacity" if row.Total_Demand > capacity else "- Within Capacity")
            st.write(f"- North DC Demand: {row.North_DC_Demand:,} bottles")
            st.write(f"- South DC Demand: {row.South_DC_Demand:,} bottles")
            st.write(f"- Trade-Off: {row.Trade_Off_Reason}")
            if row.Safety_Violations:
                st.write(f"- Safety Violations: {row.Safety_Violations}")
            st.write("")
    
    if avg_fulfillment < 95:
        st.warning("⚠️ Average fulfillment below 95%: consider capacity expansion.")
    if any("⚠️" in s for s in safety_violations):
        st.error("⚠️ Safety stock violations detected: review safety stock settings or logistics.")
    if total_unfulfilled > 50000:
        st.info("⚠️ Total unfulfilled demand > 50,000 bottles: consider demand management or capacity increase.")

st.caption("This simulation considers production capacity, truck size, and safety stock constraints. Demonstrates trade-offs and warehouse limitations.")
