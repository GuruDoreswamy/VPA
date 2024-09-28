import gradio as gr
import pandas as pd
import numpy as np
import json
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import isodate  # Required for parsing ISO 8601 duration format

# Function to parse ISO 8601 duration into a human-readable format
def parse_duration(duration_iso):
    duration = isodate.parse_duration(duration_iso)
    return duration

# Function to fetch YouTube data with pagination handling
def get_youtube_data(api_key, search_keyword, start_date, end_date):
    try:
        youtube = build('youtube', 'v3', developerKey=api_key)

        # Format dates in ISO 8601 format
        start_date_str = f"{start_date}T00:00:00Z"
        end_date_str = f"{end_date}T23:59:59Z"

        next_page_token = None
        video_data = []

        # Keep fetching videos as long as there are more pages
        while True:
            # Define search parameters
            search_response = youtube.search().list(
                q=search_keyword,
                part='id,snippet',
                maxResults=50,
                type='video',
                publishedAfter=start_date_str,
                publishedBefore=end_date_str,
                pageToken=next_page_token
            ).execute()

            for search_result in search_response['items']:
                video_id = search_result['id']['videoId']
                video_details = youtube.videos().list(part='statistics,contentDetails', id=video_id).execute()

                for video in video_details['items']:
                    view_count = int(video['statistics'].get('viewCount', 0))
                    comment_count = int(video['statistics'].get('commentCount', 0))
                    like_count = int(video['statistics'].get('likeCount', 0))
                    duration_iso = video['contentDetails'].get('duration')
                    duration = parse_duration(duration_iso)  # Convert ISO 8601 to timedelta

                    # Calculate engagement rate (likes + comments) / views * 100
                    engagement_rate = ((like_count + comment_count) / view_count * 100) if view_count > 0 else 0

                    video_data.append({
                        'Video ID': video_id,
                        'Title': search_result['snippet']['title'],
                        'Published At': search_result['snippet']['publishedAt'],
                        'View Count': view_count,
                        'Comment Count': comment_count,
                        'Like Count': like_count,
                        'Engagement Rate (%)': engagement_rate,
                        'Duration': str(duration)  # Convert timedelta to string for display
                    })

            # Get next page token to fetch more videos
            next_page_token = search_response.get('nextPageToken')
            if not next_page_token:
                break

        df = pd.DataFrame(video_data)
        return df, None

    except Exception as e:
        return None, str(e)

# Function to save metrics as a TXT file with JSON content
def save_metrics_to_txt(metrics, filename="search_metrics.txt"):
    # Convert all values in the metrics dictionary to native Python types
    metrics_serializable = {k: (int(v) if isinstance(v, np.int64) else v) for k, v in metrics.items()}
    
    with open(filename, 'w') as txt_file:
        json.dump(metrics_serializable, txt_file, indent=4)  # Save JSON as text in the file
    return filename

# Main analysis function to fetch data and generate metrics
def analyze_youtube(api_key, search_keyword, start_date, end_date):
    df, error = get_youtube_data(api_key, search_keyword, start_date, end_date)

    if error:
        return error, None, None  # Return None for CSV if error

    if df.empty:
        return "No data found for the given search parameters.", None, None

    # Calculate total metrics
    metrics = {
        'Search Keyword': search_keyword,
        'Total Videos': len(df),
        'Total Views': df['View Count'].sum(),
        'Total Comments': df['Comment Count'].sum(),
        'Total Likes': df['Like Count'].sum(),
        'Average Engagement Rate (%)': df['Engagement Rate (%)'].mean()
    }

    # Save metrics to a TXT file
    filename = save_metrics_to_txt(metrics, filename=f"{search_keyword}_metrics.txt")

    return metrics, filename, df  # Return None for CSV initially

# Function to save video details DataFrame as a CSV file
def save_video_details_to_csv(df, filename="video_details.csv"):
    df.to_csv(filename, index=False)  # Save DataFrame as CSV
    return filename

# Gradio Blocks UI
with gr.Blocks() as demo:
    gr.Markdown("# View Point Analytics")

    # Input section for YouTube API, search term, and date range
    with gr.Row():
        api_key = gr.Textbox(label="YouTube API Key", type="password")
        search_keyword = gr.Textbox(label="Search Keyword")
        start_date = gr.Textbox(label="Start Date (YYYY-MM-DD)", value=(datetime.now() - timedelta(days=30)).date().isoformat())
        end_date = gr.Textbox(label="End Date (YYYY-MM-DD)", value=datetime.now().date().isoformat())

    analyze_button = gr.Button("Analyze")

    # Metrics output and video details
    metrics_output = gr.JSON(label="Search Metrics")
    video_details_output = gr.Dataframe(label="Video Details")

    # Output for metrics and TXT file download
    txt_download_button = gr.File(label="Download TXT File")
    csv_download_button = gr.File(label="Download Video Details CSV")

    # Event: Button to trigger the analysis and get metrics
    def main_analyze(api_key, search_keyword, start_date, end_date):
        metrics, filename, df = analyze_youtube(api_key, search_keyword, start_date, end_date)

        if isinstance(metrics, str):  # Check if it's an error message
            return {"error": metrics}, None, None  # Return None for CSV if error

        # Save video details to a CSV file
        video_details_filename = save_video_details_to_csv(df, filename=f"{search_keyword}_video_details.csv")

        return metrics, filename, df, video_details_filename  # Include video details filename

    analyze_button.click(main_analyze,
                         inputs=[api_key, search_keyword, start_date, end_date],
                         outputs=[metrics_output, txt_download_button, video_details_output, csv_download_button],
                         show_progress=True)

# Launch the Gradio app
demo.launch()
