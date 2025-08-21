import os
import json
import time
import asyncio
import logging
import hashlib
import threading
import glob
from typing import Tuple, Optional, Callable, Dict, Any
from pathlib import Path

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    logging.warning("Google Drive API packages not installed. Run: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2")


class UploadManager:
    """Thread-safe upload progress manager"""
    
    def __init__(self):
        self.active_uploads: Dict[str, Dict[str, Any]] = {}
        self.upload_lock = threading.Lock()
        self.max_file_size = 5 * 1024 * 1024 * 1024  
        self.scopes = ['https://www.googleapis.com/auth/drive.file']

        os.makedirs("uploads", exist_ok=True)
        os.makedirs("temp_uploads", exist_ok=True)
        logging.info("UploadManager initialized - Max file size: 5GB")

    def get_file_hash(self, file_path: str) -> str:
        """Generate SHA256 hash for file identification"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()[:16]
        except Exception as e:
            logging.error(f"Hash calculation failed: {e}")
            return str(int(time.time()))

    def add_upload(self, upload_id: str, file_path: str, service: str, user_info: str):
        """Add new upload to tracking"""
        with self.upload_lock:
            self.active_uploads[upload_id] = {
                'file_path': file_path,
                'service': service,
                'user_info': user_info,
                'start_time': time.time(),
                'progress': 0,
                'status': 'uploading',
                'speed': '0 MB/s',
                'eta': 'Calculating...'
            }

    def update_upload_progress(self, upload_id: str, progress: int, speed: str = None, eta: str = None):
        """Update upload progress information"""
        with self.upload_lock:
            if upload_id in self.active_uploads:
                self.active_uploads[upload_id]['progress'] = progress
                if speed:
                    self.active_uploads[upload_id]['speed'] = speed
                if eta:
                    self.active_uploads[upload_id]['eta'] = eta

    def remove_upload(self, upload_id: str):
        """Remove upload from tracking"""
        with self.upload_lock:
            if upload_id in self.active_uploads:
                del self.active_uploads[upload_id]

    def get_active_uploads(self) -> Dict[str, Dict[str, Any]]:
        """Get copy of active uploads"""
        with self.upload_lock:
            return self.active_uploads.copy()


class GoogleDriveUploader:
    """Modern Google Drive uploader with OAuth2 and resumable uploads"""
    
    def __init__(self):
        self.credentials_file = "credentials.json"
        self.token_file = "token.json"
        self.scopes = ['https://www.googleapis.com/auth/drive.file']
        self.service = None
        self._lock = threading.Lock()
        
    def authenticate(self) -> bool:
        """Authenticate with Google Drive API using modern OAuth2"""
        creds = None
        
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
                logging.info("Existing token loaded successfully")
            except Exception as e:
                logging.warning(f"Failed to load existing token: {e}")
                try:
                    os.remove(self.token_file)
                except:
                    pass
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logging.info("Token refreshed successfully")
                except Exception as e:
                    logging.error(f"Token refresh failed: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.scopes)
                    
                    creds = flow.run_local_server(
                        port=8080,
                        open_browser=False,
                        timeout_seconds=300,
                        bind_addr='localhost'
                    )
                    logging.info("New authentication completed successfully")
                except Exception as e:
                    logging.error(f"OAuth flow failed: {e}")
                    raise Exception(f"Google Drive authentication failed: {e}")
            
            try:
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
                logging.info("Token saved successfully")
            except Exception as e:
                logging.warning(f"Failed to save token: {e}")
        

        try:
            self.service = build('drive', 'v3', credentials=creds, cache_discovery=False)
            
            about = self.service.about().get(fields="user").execute()
            user_email = about.get('user', {}).get('emailAddress', 'Unknown')
            logging.info(f"Google Drive service authenticated successfully for user: {user_email}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to build Google Drive service: {e}")
            self.service = None
            return False
    
    def calculate_optimal_chunk_size(self, file_size: int) -> int:
        """Calculate optimal chunk size based on file size"""
        if file_size < 50 * 1024 * 1024:
            return 1024 * 1024 
        elif file_size < 500 * 1024 * 1024:
            return 5 * 1024 * 1024 
        elif file_size < 2 * 1024 * 1024 * 1024: 
            return 10 * 1024 * 1024 
        else:
            return 25 * 1024 * 1024 
    
    def get_mime_type(self, file_path: str) -> str:
        """Get MIME type based on file extension"""
        ext = os.path.splitext(file_path)[1].lower()
        mime_types = {
            '.mp4': 'video/mp4',
            '.mkv': 'video/x-matroska',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.wmv': 'video/x-ms-wmv',
            '.flv': 'video/x-flv',
            '.webm': 'video/webm',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.flac': 'audio/flac',
            '.zip': 'application/zip',
            '.rar': 'application/x-rar-compressed',
            '.7z': 'application/x-7z-compressed'
        }
        return mime_types.get(ext, 'application/octet-stream')
    
    async def upload_with_progress(self, file_path: str, progress_callback: Optional[Callable] = None, 
                                 max_retries: int = 3) -> Tuple[bool, Any]:
        """Upload file to Google Drive with progress tracking"""
        
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"
        
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False, "File is empty (0 bytes)"
        
        filename = os.path.basename(file_path)
        logging.info(f"Starting Google Drive upload: {filename} ({file_size / (1024*1024):.1f} MB)")
        
        for attempt in range(max_retries):
            try:
                with self._lock:
                    if not self.service:
                        if not self.authenticate():
                            if attempt == max_retries - 1:
                                return False, "Authentication failed after all retries"
                            await asyncio.sleep(2 ** attempt)
                            continue
                
                file_metadata = {
                    'name': filename,
                    'description': f'Uploaded by Professional Upload System at {time.strftime("%Y-%m-%d %H:%M:%S")}',
                    'parents': []
                }
                
                chunk_size = self.calculate_optimal_chunk_size(file_size)
                mime_type = self.get_mime_type(file_path)
                
                logging.info(f"Upload config - Chunk size: {chunk_size / (1024*1024):.1f} MB, MIME: {mime_type}")
                
                media = MediaFileUpload(
                    file_path,
                    mimetype=mime_type,
                    resumable=True,
                    chunksize=chunk_size
                )
                
                request = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id,name,size,webViewLink,webContentLink,createdTime'
                )

                response = None
                last_progress = 0
                start_time = time.time()
                stall_count = 0
                retry_chunk_count = 0
                
                while response is None:
                    try:
                        status, response = request.next_chunk()
                        retry_chunk_count = 0
                        
                        if status:
                            progress = int(status.progress() * 100)
                            current_time = time.time()
                            elapsed_time = current_time - start_time
                            
                            if progress > last_progress and elapsed_time > 0:
                                bytes_uploaded = int(file_size * status.progress())
                                speed_bytes_per_sec = bytes_uploaded / elapsed_time
                                speed_mb_per_sec = speed_bytes_per_sec / (1024 * 1024)
                                
                                remaining_bytes = file_size - bytes_uploaded
                                eta_seconds = remaining_bytes / speed_bytes_per_sec if speed_bytes_per_sec > 0 else 0
                                
                                speed_text = f"{speed_mb_per_sec:.1f} MB/s"
                                if eta_seconds > 60:
                                    eta_text = f"{eta_seconds/60:.1f} min"
                                else:
                                    eta_text = f"{eta_seconds:.0f}s"
                                
                                if progress_callback:
                                    try:
                                        await progress_callback(progress, speed_text, eta_text)
                                    except Exception as cb_error:
                                        logging.warning(f"Progress callback error: {cb_error}")
                                
                                logging.info(f"Upload progress: {progress}% - Speed: {speed_text} - ETA: {eta_text}")
                                last_progress = progress
                                stall_count = 0
                            elif progress == last_progress:
                                stall_count += 1
                                if stall_count > 50:
                                    raise Exception("Upload progress stalled for too long")
                            
                            await asyncio.sleep(0.1)
                    
                    except HttpError as chunk_error:
                        retry_chunk_count += 1
                        logging.warning(f"Chunk upload error (attempt {retry_chunk_count}): {chunk_error}")
                        
                        if chunk_error.resp.status in [500, 502, 503, 504]:
                            if retry_chunk_count >= 5:
                                raise chunk_error
                            await asyncio.sleep(min(retry_chunk_count * 2, 10))
                            continue
                        else:
                            raise chunk_error
                    
                    except Exception as chunk_error:
                        retry_chunk_count += 1
                        logging.warning(f"Unexpected chunk error (attempt {retry_chunk_count}): {chunk_error}")
                        
                        if retry_chunk_count >= 3:
                            raise chunk_error
                        await asyncio.sleep(retry_chunk_count * 2)
                        continue
                
                if not response or not response.get('id'):
                    raise Exception("Upload completed but no valid response received")
                
                file_id = response.get('id')
                file_name = response.get('name')
                
                logging.info(f"File uploaded successfully - ID: {file_id}, Name: {file_name}")
                
                try:
                    permission_body = {
                        'type': 'anyone',
                        'role': 'reader'
                    }
                    
                    self.service.permissions().create(
                        fileId=file_id,
                        body=permission_body,
                        supportsAllDrives=True
                    ).execute()
                    
                    logging.info("File permissions set to public")
                except Exception as perm_error:
                    logging.warning(f"Failed to set public permissions: {perm_error}")
                
                view_link = f"https://drive.google.com/file/d/{file_id}/view"
                download_link = f"https://drive.google.com/uc?id={file_id}&export=download"
                
                upload_time = time.time() - start_time
                average_speed = (file_size / (1024 * 1024)) / upload_time if upload_time > 0 else 0
                
                logging.info(f"Upload completed successfully - Time: {upload_time/60:.1f}min, Avg Speed: {average_speed:.1f} MB/s")
                
                return True, {
                    'view_link': view_link,
                    'download_link': download_link,
                    'file_id': file_id,
                    'file_name': file_name,
                    'file_size': file_size,
                    'upload_time': upload_time,
                    'average_speed': average_speed,
                    'created_time': response.get('createdTime')
                }
                
            except HttpError as e:
                error_msg = f"Google API error (attempt {attempt + 1}): {e}"
                logging.error(error_msg)
                
                if e.resp.status == 403:
                    if "quota" in str(e).lower() or "rate" in str(e).lower():
                        return False, "Google Drive quota or rate limit exceeded"
                    else:
                        return False, "Google Drive permission denied"
                elif e.resp.status == 404:
                    return False, "Google Drive API endpoint not found"
                elif e.resp.status == 401:
                    logging.info("Authentication expired, retrying...")
                    with self._lock:
                        self.service = None
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return False, "Authentication failed"
                elif e.resp.status >= 500:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return False, f"Google Drive server error: {e.resp.status}"
                else:
                    return False, error_msg
                    
            except Exception as e:
                error_msg = f"Upload error (attempt {attempt + 1}): {str(e)}"
                logging.error(error_msg)
                
                if any(err in str(e).lower() for err in ['network', 'connection', 'timeout', 'ssl', 'socket']):
                    if attempt < max_retries - 1:
                        logging.info(f"Network error, retrying in {2 ** attempt} seconds...")
                        await asyncio.sleep(2 ** attempt)
                        continue
                
                if attempt == max_retries - 1:
                    return False, f"Upload failed after {max_retries} attempts: {str(e)}"
        
        return False, "Upload failed for unknown reason"


class VideoUploadBot:
    """Main video upload bot class"""
    
    def __init__(self):
        self.manager = UploadManager()
        self.gdrive = GoogleDriveUploader()
        self.encode_folder = "encode"
    
    def find_video_file(self, video_name: str) -> Optional[str]:
        """Find video file in encode folder"""
        if not os.path.exists(self.encode_folder):
            return None
            
        video_extensions = ['mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm', 'm4v']
        
        for ext in video_extensions:
            exact_path = os.path.join(self.encode_folder, f"{video_name}.{ext}")
            if os.path.exists(exact_path):
                return exact_path

        for ext in video_extensions:
            pattern = os.path.join(self.encode_folder, f"*{video_name}*.{ext}")
            files = glob.glob(pattern)
            if files:
                return min(files, key=os.path.getsize)
        
        return None
    
    async def upload_video(self, video_name: str, user_info: str = "Unknown", 
                          progress_callback: Optional[Callable] = None) -> Tuple[bool, Any]:
        """Upload video to Google Drive with progress tracking"""
        
        file_path = self.find_video_file(video_name)
        if not file_path:
            return False, f"Video dosyası bulunamadı: {video_name}"
        
        file_size = os.path.getsize(file_path)
        if file_size > self.manager.max_file_size:
            size_gb = file_size / (1024 * 1024 * 1024)
            return False, f"Dosya çok büyük: {size_gb:.2f}GB (max 5GB)"
        
        if file_size == 0:
            return False, "Dosya boş"
        
        upload_id = f"{int(time.time())}_{self.manager.get_file_hash(file_path)}"
        self.manager.add_upload(upload_id, file_path, "gdrive", user_info)
        
        logging.info(f"Upload started [{upload_id}]: {os.path.basename(file_path)} ({file_size / (1024*1024):.1f} MB)")
        
        async def internal_progress_callback(progress, speed="N/A", eta="N/A"):
            self.manager.update_upload_progress(upload_id, progress, speed, eta)
            if progress_callback:
                try:
                    await progress_callback(progress, speed, eta)
                except Exception as cb_error:
                    logging.warning(f"Progress callback error: {cb_error}")
        
        try:
            if not GOOGLE_DRIVE_AVAILABLE:
                return False, "Google Drive API packages not installed. Run: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
            
            success, result = await self.gdrive.upload_with_progress(
                file_path, internal_progress_callback
            )
            
            if success:
                logging.info(f"Upload completed successfully [{upload_id}]: {result.get('file_name', 'Unknown')}")
            else:
                logging.error(f"Upload failed [{upload_id}]: {result}")
            
            return success, result
                
        except Exception as e:
            logging.error(f"Upload error [{upload_id}]: {e}")
            return False, f"Upload failed: {str(e)}"
        
        finally:
            self.manager.remove_upload(upload_id)
    
    def get_active_uploads_info(self) -> str:
        """Get formatted information about active uploads"""
        active = self.manager.get_active_uploads()
        if not active:
            return "Aktif upload yok"
        
        info_lines = []
        for upload_id, info in active.items():
            elapsed = int(time.time() - info['start_time'])
            elapsed_str = f"{elapsed//60}m {elapsed%60}s" if elapsed >= 60 else f"{elapsed}s"
            
            info_lines.append(
                f"🔹 **ID:** `{upload_id}`\n"
                f"   📁 **File:** {os.path.basename(info['file_path'])}\n"
                f"   👤 **User:** {info['user_info']}\n"
                f"   📊 **Progress:** {info['progress']}%\n"
                f"   🚀 **Speed:** {info['speed']}\n"
                f"   ⏱️ **ETA:** {info['eta']}\n"
                f"   🕐 **Elapsed:** {elapsed_str}\n"
            )
        
        return "\n".join(info_lines)



uploader = VideoUploadBot()

#burayı doldurun
def setup_google_credentials():
    """Setup Google Drive API credentials"""
    credentials = {
        "installed": {
            "client_id": "",
            "project_id": "",
            "auth_uri": "",
            "token_uri": "",
            "auth_provider_x509_cert_url": "",
            "client_secret": "",
            "redirect_uris": ["http://localhost"]
        }
    }
    
    credentials_path = "credentials.json"
    if not os.path.exists(credentials_path):
        with open(credentials_path, 'w') as f:
            json.dump(credentials, f, indent=2)
        logging.info("Google Drive credentials file created")



async def upload_video_to_drive(video_name: str, user_info: str = "Unknown", 
                               progress_callback: Optional[Callable] = None) -> Tuple[bool, Any]:
    """Main function to upload video to Google Drive"""
    setup_google_credentials()
    return await uploader.upload_video(video_name, user_info, progress_callback)


def get_active_uploads_info() -> str:
    """Get information about active uploads"""
    return uploader.get_active_uploads_info()


def check_gdrive_available() -> bool:
    """Check if Google Drive API is available"""
    return GOOGLE_DRIVE_AVAILABLE