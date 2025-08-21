import asyncio
import subprocess
import os
import time
import re
import json
import logging
from typing import Optional, Callable, Dict, Any
import discord
import uuid
from datetime import datetime

class SimpleDownloadManager:
    def __init__(self):
        self.active_downloads = {}
        self.lock = asyncio.Lock()
    
    async def add_download(self, download_id: str, info: dict):
        async with self.lock:
            self.active_downloads[download_id] = info
    
    async def remove_download(self, download_id: str):
        async with self.lock:
            self.active_downloads.pop(download_id, None)
    
    async def get_download(self, download_id: str):
        async with self.lock:
            return self.active_downloads.get(download_id)

download_manager = SimpleDownloadManager()

def get_aria2_path():
    paths = ["aria2c", "aria2c.exe", r"C:\aria2\aria2c.exe", r"C:\Program Files\aria2\aria2c.exe"]
    for path in paths:
        try:
            result = subprocess.run([path, "--version"], 
                                  capture_output=True, timeout=5)
            if result.returncode == 0:
                logging.info(f"✅ Aria2c bulundu: {path}")
                return path
        except Exception as e:
            logging.debug(f"Aria2c test hatası {path}: {e}")
            continue
    
    logging.error("❌ Aria2c hiçbir yerde bulunamadı!")
    raise FileNotFoundError("❌ Aria2c bulunamadı! Lütfen aria2c'yi yükleyin ve PATH'e ekleyin.")

async def download_magnet_fast(magnet_link: str, custom_name: str, 
                              output_dir: str = "downloads", 
                              interaction: Optional[discord.Interaction] = None):
    
    download_id = str(uuid.uuid4())[:8].upper()
    start_time = time.time()
    
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        aria2_path = get_aria2_path()
    except FileNotFoundError as e:
        return False, str(e)
    

    command = [
        aria2_path,
        "--seed-time=0",
        "--dir=" + output_dir,
        "--max-connection-per-server=16",
        "--split=8", 
        "--min-split-size=1M",
        "--continue=true",
        "--file-allocation=prealloc",
        "--summary-interval=2",
        "--console-log-level=info",
        "--check-certificate=false",
        "--timeout=60",
        "--retry-wait=2",
        "--max-tries=5",
        "--bt-max-peers=50",
        "--bt-request-peer-speed-limit=50M",
        "--max-overall-download-limit=0",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        magnet_link
    ]
    
    logging.info(f"🚀 Download başlatılıyor [{download_id}]: {custom_name}")
    logging.debug(f"📝 Aria2c command: {' '.join(command[:10])}...")
    
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        await download_manager.add_download(download_id, {
            'process': process,
            'start_time': start_time,
            'status': 'downloading',
            'name': custom_name
        })
        
        progress_msg = None

        if interaction:
            try:
                embed = discord.Embed(
                    title="🚀 İndirme Başlatıldı",
                    description=f"**ID:** `{download_id}`\n**Dosya:** `{custom_name}`\n📥 Bağlantı kuruluyor...",
                    color=0x3498DB,
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"Download ID: {download_id}")
                progress_msg = await interaction.followup.send(embed=embed)
                logging.info(f"📱 Discord progress mesajı gönderildi [{download_id}]")
            except Exception as discord_error:
                logging.error(f"❌ Discord mesaj hatası [{download_id}]: {discord_error}")
        
        last_update = 0
        last_percent = 0
        max_idle_time = 300  
        max_total_time = 1800  
        

        async def read_output():
            output_lines = []
            try:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    line_str = line.decode('utf-8', errors='ignore').strip()
                    if line_str:
                        output_lines.append(line_str)
                        logging.debug(f"📝 Aria2c [{download_id}]: {line_str[:100]}")
            except Exception as e:
                logging.debug(f"Output reading error [{download_id}]: {e}")
            return output_lines
        
        output_task = asyncio.create_task(read_output())
        
        while process.returncode is None:
            try:
                current_time = time.time()
                
                if current_time - start_time > max_total_time:
                    logging.warning(f"⏰ Total timeout [{download_id}] after {max_total_time/60:.1f} minutes")
                    break
                
                try:
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                    break  
                except asyncio.TimeoutError:
                    pass  
                
                if current_time - last_update > 5: 
                    last_update = current_time
                    
                    if progress_msg:
                        try:
                            elapsed_min = int((current_time - start_time) / 60)
                            
                            embed = discord.Embed(
                                title="⬇️ İndirme Devam Ediyor",
                                description=f"**ID:** `{download_id}`\n**Dosya:** `{custom_name}`\n⏱️ Geçen süre: {elapsed_min} dakika",
                                color=0xF39C12,
                                timestamp=datetime.now()
                            )
                            embed.set_footer(text=f"Download ID: {download_id} | Aria2c Engine")
                            
                            await progress_msg.edit(embed=embed)
                            logging.debug(f"📊 Progress updated [{download_id}] - {elapsed_min} min")
                        except Exception as update_error:
                            logging.debug(f"Progress update error [{download_id}]: {update_error}")
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logging.error(f"❌ Monitoring error [{download_id}]: {e}")
                break
        
        if process.returncode is None:
            logging.info(f"⏹️ Terminating process [{download_id}]")
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=10)
            except:
                logging.warning(f"⚠️ Force killing process [{download_id}]")
                process.kill()
        
        if not output_task.done():
            output_task.cancel()
        
        await download_manager.remove_download(download_id)
        
        return_code = process.returncode
        logging.info(f"📋 Process finished [{download_id}] - Return code: {return_code}")
        
        result_file = find_downloaded_file(output_dir, custom_name)
        
        if result_file:
            file_size = os.path.getsize(result_file) / (1024 * 1024)
            download_time = int((time.time() - start_time) / 60)
            
            logging.info(f"✅ Download SUCCESS [{download_id}] - {os.path.basename(result_file)} ({file_size:.1f} MB) in {download_time} min")
            
            if progress_msg:
                try:
                    embed = discord.Embed(
                        title="✅ İndirme Tamamlandı!",
                        description=f"**Dosya:** `{os.path.basename(result_file)}`\n**Boyut:** `{file_size:.1f} MB`\n**Süre:** `{download_time} dakika`",
                        color=0x27AE60,
                        timestamp=datetime.now()
                    )
                    embed.set_footer(text=f"Download ID: {download_id} | Completed Successfully")
                    await progress_msg.edit(embed=embed)
                except Exception as success_error:
                    logging.debug(f"Success message error [{download_id}]: {success_error}")
            
            return True, os.path.basename(result_file)
        else:
            error_msg = f"İndirilen dosya bulunamadı (return code: {return_code})"
            logging.error(f"❌ {error_msg} [{download_id}]")
            
            if progress_msg:
                try:
                    embed = discord.Embed(
                        title="❌ İndirme Hatası",
                        description=f"**Hata:** {error_msg}\n**ID:** `{download_id}`",
                        color=0xE74C3C,
                        timestamp=datetime.now()
                    )
                    await progress_msg.edit(embed=embed)
                except:
                    pass
            
            return False, error_msg
            
    except Exception as e:
        error_msg = f"İndirme kritik hatası: {str(e)}"
        logging.error(f"❌ {error_msg} [{download_id}]")
        await download_manager.remove_download(download_id)
        return False, error_msg

def find_downloaded_file(output_dir: str, custom_name: str) -> Optional[str]:
    try:
        video_extensions = ['.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.m2ts']
        
        current_time = time.time()
        
        if not os.path.exists(output_dir):
            logging.error(f"❌ Output directory not found: {output_dir}")
            return None
        
        logging.info(f"🔍 Searching for downloaded files in: {output_dir}")
        
        all_files = os.listdir(output_dir)
        logging.info(f"📂 Directory contents ({len(all_files)} files):")
        for i, file in enumerate(all_files, 1):
            file_path = os.path.join(output_dir, file)
            if os.path.isfile(file_path):
                size_mb = os.path.getsize(file_path) / (1024*1024)
                mtime = os.path.getmtime(file_path)
                age_minutes = (current_time - mtime) / 60
                logging.info(f"   {i}. {file} | {size_mb:.1f} MB | {age_minutes:.1f} min ago")
            else:
                logging.info(f"   {i}. {file} | [DIRECTORY]")
        
        recent_files = []
        candidate_files = []
        
        for file in all_files:
            file_path = os.path.join(output_dir, file)
            
            if not os.path.isfile(file_path):
                continue
            
            file_size = os.path.getsize(file_path)
            file_mtime = os.path.getmtime(file_path)
            age_hours = (current_time - file_mtime) / 3600
            
            logging.info(f"🔍 Checking: {file}")
            logging.info(f"   - Size: {file_size / (1024*1024):.1f} MB")
            logging.info(f"   - Age: {age_hours:.1f} hours")
            logging.info(f"   - Extension: {os.path.splitext(file)[1].lower()}")
            

            is_video = any(file.lower().endswith(ext) for ext in video_extensions)
            logging.info(f"   - Is video: {is_video}")
            
            if is_video:
                candidate_files.append(file_path)
                logging.info(f"   ✅ Added as video candidate")
                
                if age_hours <= 3:
                    recent_files.append(file_path)
                    logging.info(f"   ✅ Added as recent file")
                else:
                    logging.info(f"   ⚠️ Too old ({age_hours:.1f}h)")
            else:
                logging.info(f"   ❌ Not a video file")
            
            if file_size < 1024 * 1024: 
                logging.info(f"   ⚠️ File too small ({file_size} bytes)")
            
            logging.info(f"   ---")
        
        logging.info(f"📊 Analysis results:")
        logging.info(f"   - Total files: {len(all_files)}")
        logging.info(f"   - Video candidates: {len(candidate_files)}")
        logging.info(f"   - Recent files: {len(recent_files)}")
        
        target_files = recent_files if recent_files else candidate_files
        
        if not target_files:
            logging.error(f"❌ No valid files found!")
            
            temp_patterns = ['.aria2', '.part', '.downloading', '*.tmp']
            temp_files = []
            for file in all_files:
                if any(pattern.replace('*', '') in file.lower() for pattern in temp_patterns):
                    temp_files.append(file)
            
            if temp_files:
                logging.warning(f"⚠️ Found temp files (download might be in progress): {temp_files}")
                return None
            
            logging.warning(f"🔄 Desperate mode: trying any recent file > 10MB")
            for file in all_files:
                file_path = os.path.join(output_dir, file)
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    age = (current_time - os.path.getmtime(file_path)) / 3600
                    if size > 10 * 1024 * 1024 and age <= 2:
                        logging.warning(f"🎯 Desperate pick: {file} ({size/(1024*1024):.1f} MB)")
                        return file_path
            
            return None
        
        largest_file = max(target_files, key=os.path.getsize)
        largest_size = os.path.getsize(largest_file) / (1024*1024)
        
        logging.info(f"✅ Selected largest file: {os.path.basename(largest_file)} ({largest_size:.1f} MB)")
        
        if custom_name:
            ext = os.path.splitext(largest_file)[1] or '.mkv'
            new_name = custom_name + ext
            new_path = os.path.join(output_dir, new_name)
            
            try:
                if os.path.exists(new_path) and new_path != largest_file:
                    os.remove(new_path)
                    logging.info(f"🗑️ Removed existing: {new_name}")
                
                if largest_file != new_path:
                    os.rename(largest_file, new_path)
                    logging.info(f"📝 Renamed to: {new_name}")
                
                return new_path
            except Exception as rename_error:
                logging.warning(f"⚠️ Rename failed: {rename_error}")
                return largest_file
        
        return largest_file
        
    except Exception as e:
        logging.error(f"❌ File search critical error: {e}")
        import traceback
        logging.error(f"❌ Traceback: {traceback.format_exc()}")
        return None

async def download_magnet_with_progress(magnet_link: str, 
                                      progress_callback: Optional[Callable] = None,
                                      custom_name: Optional[str] = None,
                                      output_dir: str = "downloads",
                                      user_info: str = "Unknown",
                                      interaction: Optional[discord.Interaction] = None):
    return await download_magnet_fast(
        magnet_link=magnet_link,
        custom_name=custom_name or "download",
        output_dir=output_dir,
        interaction=interaction
    )

def get_active_downloads_info():
    try:
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return "Aktif download bilgisi alınamadı (async context)"
            else:
                downloads = loop.run_until_complete(_get_active_downloads_async())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            downloads = loop.run_until_complete(_get_active_downloads_async())
            loop.close()
        
        if not downloads:
            return "Aktif indirme yok"
        
        info = []
        for dl_id, data in downloads.items():
            elapsed = int(time.time() - data['start_time'])
            elapsed_str = f"{elapsed//60}m {elapsed%60}s" if elapsed >= 60 else f"{elapsed}s"
            info.append(f"🔹 **ID:** `{dl_id}` | **Dosya:** `{data.get('name', 'Unknown')}` | **Süre:** `{elapsed_str}`")
        
        return "\n".join(info)
    except Exception as e:
        logging.error(f"❌ get_active_downloads_info error: {e}")
        return "Bilgi alınamadı"

async def _get_active_downloads_async():
    """Async helper function"""
    async with download_manager.lock:
        return download_manager.active_downloads.copy()

def cancel_all_downloads(cancelled_by: str):
    return 0