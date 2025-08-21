# Encoder Bot 🤖

Professional Discord bot for automated video processing, magnet link downloading, and Google Drive integration. Built with modern Python technologies and designed for content creators and video enthusiasts.

**Developed by [LeonisDev0](https://github.com/LeonisDev0 Discord: leonis1337 )** 🚀

## ✨ Features

### 🎯 Core Functionality
- **Magnet Link Downloader** - Fast torrent downloading using Aria2c with progress tracking
- **Video Encoder** - Professional video processing with FFmpeg (intro + video + subtitle merging)
- **Google Drive Uploader** - Automated cloud storage integration with OAuth2
- **Discord Bot Interface** - Modern slash command system with rich embeds
- **Progress Tracking** - Real-time operation monitoring with visual progress bars
- **Statistics System** - Comprehensive bot analytics and performance metrics

### 🔧 Technical Features
- **Multi-threaded Processing** - Concurrent download, encode, and upload operations
- **Resumable Operations** - Interrupted processes can be resumed automatically
- **Advanced Error Handling** - Robust error management and recovery systems
- **Comprehensive Logging** - Detailed operation logs with file rotation
- **Resource Management** - CPU, memory, and disk usage optimization
- **Cross-platform Support** - Windows, Linux, and macOS compatibility

## 📋 Requirements

### System Requirements
- **Python 3.8+** - [Download](https://www.python.org/downloads/)
- **FFmpeg** - [Download](https://ffmpeg.org/download.html)
- **Aria2c** - [Download](https://aria2.github.io/)

### Python Dependencies
```
discord.py>=2.3.0
PyNaCl>=1.5.0
google-api-python-client>=2.70.0
google-auth-httplib2>=0.1.0
google-auth-oauthlib>=0.8.0
psutil>=5.9.0
requests>=2.28.0
urllib3>=1.26.0
certifi>=2022.0.0
six>=1.16.0
packaging>=21.0
```

## 🚀 Installation

### 1. Clone Repository
```bash
git clone [repository-url]
cd Encoder-Bot-main
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Setup External Tools

#### FFmpeg Installation
- **Windows**: Download from [FFmpeg.org](https://ffmpeg.org/download.html)
  - Extract to `C:\ffmpeg\bin\` or add to system PATH
- **Linux**: `sudo apt install ffmpeg`
- **macOS**: `brew install ffmpeg`

#### Aria2c Installation
- **Windows**: Download from [Aria2 GitHub](https://github.com/aria2/aria2/releases)
  - Extract to `C:\aria2\` or add to system PATH
- **Linux**: `sudo apt install aria2`
- **macOS**: `brew install aria2`

### 4. Discord Bot Setup
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create new application
3. Navigate to Bot section
4. Copy bot token
5. Enable required permissions:
   - Send Messages
   - Use Slash Commands
   - Attach Files
   - Read Message History
   - Embed Links

### 5. Google Drive API Setup
1. Visit [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project or select existing
3. Enable Google Drive API
4. Create OAuth 2.0 credentials
5. Download `credentials.json` to project root

### 6. Configuration Files
Create `bot_token.txt` in project root:
```
YOUR_DISCORD_BOT_TOKEN_HERE
```

## 📖 Usage

### Discord Commands

#### `/indir` - Download Video
```
/indir magnet_link:MAGNET_LINK filename:VIDEO_NAME
```
Downloads video from magnet link with custom filename.

**Example:**
```
/indir magnet_link:magnet:?xt=urn:btih:... filename:my_video
```

#### `/encode` - Process Video
```
/encode intro:intro.mp4 episode:video.mkv subtitle_file:subtitle.ass subtitle_name:sub.ass
```
Combines intro, main video, and subtitle into single MP4 file.

**Example:**
```
/encode intro:intro.mp4 episode:episode01.mkv subtitle_file:subtitle.ass subtitle_name:sub.ass
```

#### `/upload` - Upload to Google Drive
```
/upload video_name:encoded_video.mp4
```
Uploads processed video from `encode/` folder to Google Drive.

#### `/downloads` - View Downloads
Shows active downloads and files in downloads folder.

#### `/encodestats` - Encoding Statistics
Displays active encoding processes and statistics.

#### `/uploads` - Upload Manager
Shows active uploads and Google Drive status.

### File Structure
```
Encoder-Bot-main/
├── bot.py              # Main Discord bot with slash commands
├── encoder.py          # Video processing engine (FFmpeg)
├── downloader.py       # Magnet link downloader (Aria2c)
├── uploader.py         # Google Drive integration
├── stats.py            # Statistics and analytics system
├── requirements.txt    # Python dependencies
├── bot_token.txt      # Discord bot token
├── credentials.json   # Google Drive API credentials
├── downloads/         # Downloaded files
├── encode/           # Encoded videos
├── uploads/          # Files ready for upload
├── temp/             # Temporary files
├── logs/             # Operation logs
├── encodelog/        # Encoding process logs
└── subs/             # Subtitle files (temporary)
```

## 🔧 Configuration

### Environment Variables
```bash

FFMPEG_PATH=/usr/bin/ffmpeg
ARIA2C_PATH=/usr/bin/aria2c
DOWNLOAD_DIR=downloads
ENCODE_DIR=encode
UPLOAD_DIR=uploads
```

### Bot Settings
- **Max Concurrent Downloads**: 3 (configurable in `downloader.py`)
- **Max Concurrent Encodes**: 3 (configurable in `encoder.py`)
- **Max File Size**: 5GB (configurable in `uploader.py`)
- **Log Level**: INFO (configurable in logging setup)

### Download Settings (Aria2c)
- **Max Connections**: 16 per server
- **Split Size**: 8 segments
- **Min Split**: 1MB
- **Max Peers**: 50
- **Seed Time**: 0 (no seeding)

## 📊 Monitoring

### Real-time Statistics
- Active downloads and encodes
- System resource usage
- Operation success rates
- Performance metrics
- Daily/weekly/monthly statistics

### Log Files
- `logs/bot_*.log` - Bot operation logs with timestamps
- `encodelog/encode_*.log` - Individual encoding process logs
- Console output with colored log levels
- Automatic log rotation

### Progress Tracking
- Visual progress bars for all operations
- Real-time speed and ETA information
- Status updates via Discord embeds
- Error reporting and recovery

### Performance Optimization
- **Download Speed**: Adjust Aria2c parameters in `downloader.py`
- **Encoding Quality**: Modify FFmpeg parameters in `encoder.py`
- **Memory Usage**: Limit concurrent operations in respective modules
- **Disk Space**: Monitor temporary file cleanup

### Log Analysis
- Check `logs/` directory for error details
- Review encoding logs in `encodelog/`
- Monitor console output for real-time issues
- Use Discord command responses for status

### Resource Usage
- **CPU**: 20-80% during encoding
- **Memory**: 100MB-2GB depending on video size
- **Disk**: Temporary storage for processing files
- **Network**: Optimized for high-bandwidth operations

## 🔄 Updates

### Version History
- **v2.0**: Enhanced error handling and logging
- **v1.5**: Google Drive integration improvements
- **v1.0**: Initial release with core functionality

### Planned Features
- [ ] Web-based control panel
- [ ] Multiple video format support
- [ ] Advanced subtitle handling
- [ ] Cloud storage alternatives
- [ ] API rate limit optimization
- [ ] Docker containerization


git clone [repository-url]
cd Discord-Encoder-Bot

# Install development dependencies
pip install -r requirements.txt

# Run bot
python bot.py
```

## 📞 Support
**(Discord: Leonis1337 )**
**Developed by [LeonisDev0](https://github.com/LeonisDev0)**
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
