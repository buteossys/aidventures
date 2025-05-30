FROM python:3.9

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Rest of your Dockerfile... 