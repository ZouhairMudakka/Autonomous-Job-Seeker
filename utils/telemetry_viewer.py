"""
Telemetry Viewer - Interactive visualization of telemetry data
"""

import streamlit as st
from pathlib import Path
import json
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any
import openai  # Optional: for GPT integration

class TelemetryViewer:
    def __init__(self):
        self.data_dir = Path('./data/telemetry/events')
        self.metrics_dir = Path('./data/telemetry/metrics')
        
    def load_events(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Load events within date range."""
        all_events = []
        for file in self.data_dir.glob("events_*.json"):
            date_str = file.stem.split('_')[1]
            if self._is_date_in_range(date_str, start_date, end_date):
                with file.open('r') as f:
                    all_events.extend(json.load(f))
        return all_events

    def _is_date_in_range(self, date_str: str, start: str = None, end: str = None) -> bool:
        """Check if date is within range."""
        date = datetime.strptime(date_str, "%Y-%m-%d")
        if start:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            if date < start_date:
                return False
        if end:
            end_date = datetime.strptime(end, "%Y-%m-%d")
            if date > end_date:
                return False
        return True

    def analyze_events(self, events: List[Dict]) -> Dict[str, Any]:
        """Generate analytics from events."""
        if not events:
            return {}
            
        df = pd.DataFrame(events)
        
        analytics = {
            'total_events': len(events),
            'success_rate': (df['success'].mean() * 100),
            'event_types': df['event_type'].value_counts().to_dict(),
            'avg_confidence': df['confidence_score'].mean(),
            'daily_events': df.groupby(df['timestamp'].str[:10]).size().to_dict()
        }
        
        return analytics

def main():
    st.title("Telemetry Viewer")
    viewer = TelemetryViewer()

    # Date Range Selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date")
    with col2:
        end_date = st.date_input("End Date")

    # Load and analyze data
    events = viewer.load_events(
        start_date.strftime("%Y-%m-%d") if start_date else None,
        end_date.strftime("%Y-%m-%d") if end_date else None
    )
    
    analytics = viewer.analyze_events(events)
    
    if not analytics:
        st.warning("No data found for selected date range")
        return

    # Display Key Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Events", analytics['total_events'])
    with col2:
        st.metric("Success Rate", f"{analytics['success_rate']:.1f}%")
    with col3:
        st.metric("Avg Confidence", f"{analytics.get('avg_confidence', 0):.2f}")

    # Event Types Chart
    st.subheader("Event Types Distribution")
    fig = px.bar(
        x=list(analytics['event_types'].keys()),
        y=list(analytics['event_types'].values()),
        labels={'x': 'Event Type', 'y': 'Count'}
    )
    st.plotly_chart(fig)

    # Daily Events Timeline
    st.subheader("Daily Events Timeline")
    daily_df = pd.DataFrame(
        list(analytics['daily_events'].items()),
        columns=['Date', 'Events']
    )
    fig = px.line(daily_df, x='Date', y='Events')
    st.plotly_chart(fig)

    # Optional: GPT Analysis
    if st.checkbox("Enable GPT Analysis"):
        prompt = st.text_area("Ask a question about the telemetry data:")
        if prompt and st.button("Analyze"):
            # Simple GPT prompt about the analytics
            system_prompt = f"""
            Analyze this telemetry data:
            - Total Events: {analytics['total_events']}
            - Success Rate: {analytics['success_rate']:.1f}%
            - Average Confidence: {analytics.get('avg_confidence', 0):.2f}
            - Event Types: {analytics['event_types']}
            
            User Question: {prompt}
            """
            # Add your GPT integration here
            st.write("GPT Analysis will be added here")

if __name__ == "__main__":
    main() 