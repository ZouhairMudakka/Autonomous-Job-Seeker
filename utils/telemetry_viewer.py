"""
Telemetry Viewer - Interactive visualization of telemetry data + Universal Model integration
"""

import os
import streamlit as st
from pathlib import Path
import json
from datetime import datetime
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any

# Instead of importing openai directly, we'll import our universal_model module:
# Make sure you have universal_model.py in your project path.
from universal_model import ModelSelector

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
        """Check if the file date is within user-selected range."""
        file_date = datetime.strptime(date_str, "%Y-%m-%d")
        if start:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            if file_date < start_date:
                return False
        if end:
            end_date = datetime.strptime(end, "%Y-%m-%d")
            if file_date > end_date:
                return False
        return True

    def analyze_events(self, events: List[Dict]) -> Dict[str, Any]:
        """Generate analytics from events."""
        if not events:
            return {}
            
        df = pd.DataFrame(events)
        
        analytics = {
            'total_events': len(events),
            'success_rate': (df['success'].mean() * 100) if 'success' in df else 0.0,
            'event_types': df['event_type'].value_counts().to_dict() if 'event_type' in df else {},
            'avg_confidence': df['confidence_score'].mean() if 'confidence_score' in df else 0.0,
            'daily_events': {}
        }
        
        # If we have timestamps, group by date
        if 'timestamp' in df:
            df['date'] = df['timestamp'].apply(lambda x: x[:10])  # first 10 chars => 'YYYY-MM-DD'
            daily_counts = df.groupby('date').size().to_dict()
            analytics['daily_events'] = daily_counts
        
        return analytics

def main():
    st.title("Telemetry Viewer (with Universal Model)")

    viewer = TelemetryViewer()

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date")
    with col2:
        end_date = st.date_input("End Date")

    # Convert date inputs to strings
    start_str = start_date.strftime("%Y-%m-%d") if start_date else None
    end_str = end_date.strftime("%Y-%m-%d") if end_date else None

    # 1. Load events and analyze
    events = viewer.load_events(start_str, end_str)
    analytics = viewer.analyze_events(events)
    
    if not analytics:
        st.warning("No data found for selected date range")
        return

    # 2. Display Key Metrics
    colA, colB, colC = st.columns(3)
    with colA:
        st.metric("Total Events", analytics['total_events'])
    with colB:
        st.metric("Success Rate", f"{analytics['success_rate']:.1f}%")
    with colC:
        st.metric("Avg Confidence", f"{analytics['avg_confidence']:.2f}")

    # 3. Event Types Chart
    st.subheader("Event Types Distribution")
    event_types = analytics.get('event_types', {})
    if event_types:
        fig = px.bar(
            x=list(event_types.keys()),
            y=list(event_types.values()),
            labels={'x': 'Event Type', 'y': 'Count'}
        )
        st.plotly_chart(fig)

    # 4. Daily Events Timeline
    daily_events = analytics.get('daily_events', {})
    if daily_events:
        st.subheader("Daily Events Timeline")
        daily_df = pd.DataFrame(list(daily_events.items()), columns=['Date', 'Events'])
        fig2 = px.line(daily_df, x='Date', y='Events')
        st.plotly_chart(fig2)

    # 5. GPT Analysis (with universal_model)
    st.subheader("AI (GPT) Analysis")
    st.write("You can ask a question about the telemetry data. We'll pass a summary + your question to the chosen model.")

    # Let the user pick a model from possible choices
    # You can adapt these to the actual model names your universal_model handles:
    model_choice = st.selectbox(
        "Select Model",
        ["gpt-3.5-turbo", "gpt-4", "deepseek-chat", "deepseek-reasoner", "gpt-4o-mini"]
    )

    enable_gpt = st.checkbox("Enable GPT Analysis?")
    if enable_gpt:
        user_question = st.text_area("Enter your question about the telemetry data:")
        if st.button("Analyze with GPT"):
            if not user_question.strip():
                st.warning("Please enter a question.")
            else:
                # Build a short system prompt describing the analytics
                system_prompt = f"""
                Here is a short summary of telemetry:

                Total Events: {analytics.get('total_events', 0)}
                Success Rate: {analytics.get('success_rate', 0):.1f}%
                Avg Confidence: {analytics.get('avg_confidence', 0):.2f}
                Event Types: {event_types}
                Daily Events: {daily_events}

                The user will ask a question related to these stats. Answer concisely.
                """

                from universal_model import ModelSelector
                selector = ModelSelector()

                try:
                    response = selector.chat_completion(
                        model=model_choice,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_question}
                        ],
                        temperature=0.7,
                    )
                    st.write("### GPT Response")
                    st.write(response)
                except Exception as e:
                    st.error(f"Error calling model: {e}")


if __name__ == "__main__":
    main()
