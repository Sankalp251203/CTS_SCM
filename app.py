# --- Trade-off Trends (Weekly) ---
st.subheader("Trade-off Trends by Week (Forecast + Annotations)")

# Build a trend dataframe from detailed_analysis
trend_df = pd.DataFrame(detailed_analysis)

# Flags and severity index
trend_df["Capacity_Shortfall"] = (trend_df["Total_Demand"] - capacity).clip(lower=0).astype(int)
trend_df["Safety_Flag"] = trend_df["Safety_Violation"].astype(str).str.len().gt(0).astype(int)
trend_df["Tradeoff_Flag"] = trend_df["Trade_Off_Reason"].astype(str).str.contains("⚠️").astype(int)

# Simple severity index: normalize shortfall by capacity and add 0.5 if safety violation
trend_df["Severity_Index"] = (trend_df["Capacity_Shortfall"] / capacity).round(3) + 0.5 * trend_df["Safety_Flag"]

# Short annotation text
trend_df["Tradeoff_Annotation"] = np.where(
    trend_df["Tradeoff_Flag"].eq(1),
    trend_df["Trade_Off_Reason"].str.replace("⚠️ ", "", regex=False).str.slice(0, 40) + "...",
    "No trade-off"
)

# Show the computed trend table
st.dataframe(
    trend_df[["Week","Total_Demand","Total_Produced","Capacity_Shortfall","Safety_Flag","Severity_Index","Trade_Off_Reason"]],
    use_container_width=True
)

# Forecast & trade-off trend line chart
fig_trend = go.Figure()

# Demand forecast line
fig_trend.add_trace(
    go.Scatter(
        x=trend_df["Week"], y=trend_df["Total_Demand"],
        mode="lines+markers", name="Forecast Demand",
        line=dict(width=3, color="#1f77b4")
    )
)

# Planned production line
fig_trend.add_trace(
    go.Scatter(
        x=trend_df["Week"], y=trend_df["Total_Produced"],
        mode="lines+markers", name="Planned Production",
        line=dict(width=3, color="#2ca02c")
    )
)

# Trade-off severity line (scaled to capacity for same axis; optional second axis if preferred)
fig_trend.add_trace(
    go.Scatter(
        x=trend_df["Week"],
        y=(trend_df["Severity_Index"] * capacity),  # scale so it is visible on same axis
        mode="lines+markers",
        name="Trade-off Severity (scaled)",
        line=dict(width=2, dash="dot", color="#d62728")
    )
)

# Capacity reference line
fig_trend.add_hline(
    y=capacity, line_width=2, line_dash="dash", line_color="red",
    annotation_text="Plant Capacity", annotation_position="top right"
)

# Add text annotations at demand points to describe weekly trade-offs
fig_trend.add_trace(
    go.Scatter(
        x=trend_df["Week"],
        y=trend_df["Total_Demand"],
        mode="markers+text",
        text=trend_df["Tradeoff_Annotation"],
        textposition="top center",
        name="Trade-off Notes",
        marker=dict(size=1, color="rgba(0,0,0,0)")  # invisible marker, text only
    )
)

fig_trend.update_layout(
    title="Weekly Forecast vs Production with Trade-off Trends",
    xaxis_title="Week",
    yaxis_title="Bottles",
    legend_title="Series",
    hovermode="x unified"
)

st.plotly_chart(fig_trend, use_container_width=True)
