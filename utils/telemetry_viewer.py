"""
Telemetry Viewer - Interactive visualization of telemetry data + Universal Model integration

This version:
1. Dynamically loads the recognized model names from universal_model.ModelSelector
2. If user doesn't pick a model, we fall back to the default from universal_model (DEFAULT_TEXT_MODEL)
3. Max tokens also default to whatever universal_model logic dictates
4. The user can optionally override model or token count in the UI

Future Enhancements:
-------------------
1. Conversation Explorer:
   - Add dedicated chat analysis tab
   - Show conversation threads
   - Display message pairs
   - Track conversation outcomes
   - Visualize chat patterns

2. Enhanced Analytics Views:
   - Token usage charts
   - Cost analysis dashboard
   - Response time graphs
   - Success rate visualizations
   - User session analysis
   - Peak usage patterns

3. AI Analysis Features:
   - Conversation pattern detection
   - Usage trend analysis
   - Anomaly detection
   - Performance insights
   - Cost optimization suggestions

4. Interactive Features:
   - Conversation replay
   - Message search
   - Pattern filtering
   - Custom date ranges
   - Export capabilities

5. Performance Monitoring:
   - Real-time alerts
   - Model performance comparison
   - Error rate tracking
   - Resource usage visualization
"""

import os
import streamlit as st
from pathlib import Path
import json
from datetime import datetime
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any

# Import the universal model
from universal_model import ModelSelector

class TelemetryViewer:
    def __init__(self):
        self.data_dir = Path('./data/telemetry/events')
        self.metrics_dir = Path('./data/telemetry/metrics')
        
    def load_events(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Load events within date range from local JSON logs."""
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
    st.write("Query the telemetry data using a universal model interface.")

    # Step A: Instantiate ModelSelector (once)
    selector = ModelSelector()

    # Step B: Let user pick a model from a combined list or fallback to 'None'
    # so that universal model can handle defaults
    all_known_models = (
        selector.OPENAI_MODELS
        + selector.DEEPSEEK_MODELS
        + selector.MODEL_BOX_MODELS
    )
    all_known_models = sorted(list(set(all_known_models)))  # remove duplicates, sort

    with st.expander("Advanced Model Selection"):
        chosen_model = st.selectbox(
            "Select a Model (or leave None for universal default)",
            [None] + all_known_models,
            format_func=lambda x: x if x else "None (use universal default)"
        )
        user_max_tokens = st.number_input("Max Tokens (0 = let universal model decide)", min_value=0, value=0)

    enable_gpt = st.checkbox("Enable GPT Analysis?")
    if enable_gpt:
        user_question = st.text_area("Enter your question about the telemetry data:", "")
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

                try:
                    # If user picked 0, let universal model handle default. If > 0, pass it in.
                    max_tokens_override = None if user_max_tokens == 0 else user_max_tokens

                    response = selector.chat_completion(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_question}
                        ],
                        model=chosen_model,  # can be None
                        max_tokens=max_tokens_override
                    )
                    st.write("### GPT Response")
                    st.write(response)
                except Exception as e:
                    st.error(f"Error calling model: {e}")


if __name__ == "__main__":
    main()
