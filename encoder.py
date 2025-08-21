import subprocess
import os
import asyncio
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import json
import re
from pathlib import Path

try:
    import discord
except ImportError:
    discord = None

try:
    import psutil
except ImportError:
    psutil = None

class FastVideoEncoder:
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler('encoder.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        self.ffmpeg_path = self._find_ffmpeg()
        self.output_dir = "encode"
        os.makedirs(self.output_dir, exist_ok=True)
        self.max_concurrent_encodes = 3
        self.active_encodes = {}
        self.encode_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent_encodes)
        
        self.logger.info("FastVideoEncoder başlatıldı")

    def _setup_logger(self, encode_id):
        log_dir = "encodelog"
        os.makedirs(log_dir, exist_ok=True)
        
        logger = logging.getLogger(f"encode_{encode_id}")
        logger.setLevel(logging.DEBUG)
        
        if logger.hasHandlers():
            logger.handlers.clear()
            
        fh = logging.FileHandler(
            os.path.join(log_dir, f"encode_{encode_id}.log"), 
            encoding='utf-8'
        )
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        return logger

    def _find_ffmpeg(self):
        paths = [
            "ffmpeg",
            "ffmpeg.exe", 
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"D:\ffmpeg\bin\ffmpeg.exe"
        ]
        
        for path in paths:
            try:
                result = subprocess.run(
                    [path, "-version"], 
                    capture_output=True, 
                    timeout=10,
                    text=True
                )
                if result.returncode == 0:
                    print(f"FFmpeg bulundu: {path}")
                    return path
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue
                
        raise FileNotFoundError("FFmpeg bulunamadı! Lütfen FFmpeg'i kurun ve PATH'e ekleyin.")

    def find_video_file(self, filename):
        search_dirs = ["downloads", ".", "videos", "input", "temp"]
        
        for directory in search_dirs:
            if os.path.exists(directory):
                full_path = os.path.join(directory, filename)
                if os.path.exists(full_path):
                    return full_path
                    
                for ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv']:
                    full_path_with_ext = os.path.join(directory, filename + ext)
                    if os.path.exists(full_path_with_ext):
                        return full_path_with_ext
        
        if os.path.exists(filename):
            return filename
            
        return None

    def can_start_new_encode(self):
        with self.encode_lock:
            return len(self.active_encodes) < self.max_concurrent_encodes

    def get_active_encode_count(self):
        with self.encode_lock:
            return len(self.active_encodes)

    def add_active_encode(self, encode_id, user_info):
        with self.encode_lock:
            self.active_encodes[encode_id] = {
                'user': user_info,
                'start_time': time.time(),
                'status': 'running'
            }

    def remove_active_encode(self, encode_id):
        with self.encode_lock:
            if encode_id in self.active_encodes:
                del self.active_encodes[encode_id]

    def get_active_encodes_info(self):
        with self.encode_lock:
            return self.active_encodes.copy()

    def stop_encode(self, encode_id):
        with self.encode_lock:
            if encode_id in self.active_encodes:
                if psutil:
                    for proc in psutil.process_iter(['pid', 'cmdline']):
                        try:
                            if proc.info['cmdline'] and 'ffmpeg' in ' '.join(proc.info['cmdline']):
                                if encode_id in ' '.join(proc.info['cmdline']):
                                    proc.terminate()
                                    time.sleep(2)
                                    if proc.is_running():
                                        proc.kill()
                                    break
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                
                self.active_encodes[encode_id]['status'] = 'stopped'
                return True
        return False

    def _get_video_duration(self, video_path):
        try:
            ffprobe_path = self.ffmpeg_path.replace('ffmpeg', 'ffprobe')
            
            cmd = [
                ffprobe_path, "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                self.logger.info(f"🕐 Duration (FFprobe): {video_path} = {duration:.2f}s")
                return duration
            else:
                return self._get_duration_fallback(video_path)
                
        except Exception as e:
            self.logger.warning(f"FFprobe duration alma hatası: {e}")
            return self._get_duration_fallback(video_path)

    def _get_duration_fallback(self, video_path):
        try:
            cmd = [self.ffmpeg_path, "-i", video_path, "-f", "null", "-"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            stderr = result.stderr
            
            duration_match = re.search(r'Duration: (\d{2}):(\d{2}):(\d{2})\.(\d{2})', stderr)
            if duration_match:
                hours = int(duration_match.group(1))
                minutes = int(duration_match.group(2))
                seconds = int(duration_match.group(3))
                centiseconds = int(duration_match.group(4))
                total_seconds = hours * 3600 + minutes * 60 + seconds + centiseconds/100
                
                self.logger.info(f"🕐 Duration (fallback): {video_path} = {total_seconds:.2f}s")
                return total_seconds
                
        except Exception as e:
            self.logger.error(f"Duration fallback hatası: {e}")
            
        return None

    def test_simple_encode(self, input_file):
        try:
            output_file = os.path.join(self.output_dir, "test_output.mp4")
            
            cmd = [
                self.ffmpeg_path, "-y",
                "-i", input_file,
                "-t", "10",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",
                "-c:a", "aac",
                "-movflags", "+faststart",
                output_file
            ]
            
            self.logger.info(f"🔧 Test komutu: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            self.logger.info(f"🔧 Return code: {result.returncode}")
            if result.stderr:
                self.logger.debug(f"🔧 STDERR: {result.stderr[-500:]}")
            
            if os.path.exists(output_file):
                size = os.path.getsize(output_file)
                self.logger.info(f"✅ Test başarılı! Çıktı dosyası: {size} bytes")
                
                try:
                    os.remove(output_file)
                except:
                    pass
                    
                return True
            else:
                self.logger.error("❌ Çıktı dosyası oluşmadı")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Test encode hatası: {e}")
            return False

    def _validate_subtitle_file(self, subtitle_path):
        try:
            with open(subtitle_path, 'r', encoding='utf-8-sig') as f:
                content = f.read().strip()
            
            if not content:
                raise ValueError("Altyazı dosyası boş")
            
            if not ('[Script Info]' in content or '[V4 Styles]' in content or '[V4+ Styles]' in content):
                raise ValueError("Geçersiz ASS/SSA format")
            
            subtitle_path_fixed = subtitle_path.replace('\\', '/').replace(':', '\\:')
            
            self.logger.info(f"✅ Subtitle validated: {len(content)} chars")
            return subtitle_path_fixed, True
            
        except Exception as e:
            self.logger.error(f"❌ Subtitle validation error: {e}")
            return subtitle_path, False

    def _run_simple_encoding(self, intro_path, episode_path, output_path, subtitle_path, encode_id, progress_callback=None):
        logger = self._setup_logger(encode_id)
        start_time = time.time()
        logger.info(f"🎬 Encoding started for ID: {encode_id}")

        try:
            files_to_check = [
                ("Intro", intro_path),
                ("Episode", episode_path),
                ("Subtitle", subtitle_path)
            ]
            
            for name, path in files_to_check:
                if not os.path.exists(path):
                    error_msg = f"{name} dosyası bulunamadı: {path}"
                    logger.error(error_msg)
                    return {'success': False, 'message': error_msg}
                else:
                    size = os.path.getsize(path) / (1024*1024)
                    logger.info(f"✅ {name}: {path} ({size:.1f} MB)")

            intro_duration = self._get_video_duration(intro_path) or 10.0
            episode_duration = self._get_video_duration(episode_path) or 1400.0
            total_duration = intro_duration + episode_duration
            
            logger.info(f"📊 Video durations - Intro: {intro_duration:.1f}s, Episode: {episode_duration:.1f}s, Total: {total_duration:.1f}s")

            subtitle_path_safe, is_valid = self._validate_subtitle_file(subtitle_path)
            if not is_valid:
                return {'success': False, 'message': 'Altyazı dosyası hatalı'}

            logger.info("🔧 Single-pass encoding: Concat + Subtitle")
            
            filter_complex = (
                "[0:v]fps=25,scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[intro_v];"
                "[1:v]fps=25,scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[episode_v];"
                "[0:a]aresample=48000[intro_a];"
                "[1:a]aresample=48000[episode_a];"
                "[intro_v][intro_a][episode_v][episode_a]concat=n=2:v=1:a=1[concat_v][concat_a];"
                f"[concat_v]ass='{subtitle_path_safe}',setpts=PTS+{intro_duration}/TB[v]"
            )

            command = [
                self.ffmpeg_path, "-y",
                "-i", intro_path,
                "-i", episode_path,
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", "[concat_a]",
                "-c:v", "libx264",
                "-preset", "veryfast",       
                "-crf", "23",                
                "-c:a", "aac",
                "-b:a", "128k",
                "-r", "25",
                "-movflags", "+faststart",
                output_path
            ]

            logger.info(f"🔧 FFmpeg command: {' '.join(command)}")

            result = self._run_ffmpeg_process(
                command, 
                encode_id, 
                logger, 
                total_duration,
                progress_callback,
                0
            )

            if not result['success']:
                return result

            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                duration = time.time() - start_time

                if file_size > 10240:
                    logger.info(f"✅ Encoding completed: {encode_id} - {file_size/(1024*1024):.1f} MB, duration: {duration:.1f}s")
                    
                    if progress_callback:
                        progress_callback(100)
                    
                    return {
                        'success': True,
                        'file_size': file_size,
                        'duration': duration,
                        'message': f'Video başarıyla oluşturuldu! ({duration/60:.1f} dakika)'
                    }
                else:
                    logger.error(f"Output file too small: {file_size} bytes")
                    return {'success': False, 'message': f'Çıktı dosyası çok küçük: {file_size} bytes'}
            else:
                logger.error("Output file not found after encoding")
                return {'success': False, 'message': 'Encode sonrası çıktı dosyası bulunamadı'}

        except Exception as e:
            logger.exception(f"Exception during encoding: {str(e)}")
            return {'success': False, 'message': f'Hata: {str(e)}'}

    def _run_ffmpeg_process(self, command, encode_id, logger, expected_duration, progress_callback=None, progress_offset=0):
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            stderr_output = ""
            current_progress = progress_offset

            while True:
                stderr_line = process.stderr.readline()
                
                if stderr_line:
                    stderr_output += stderr_line
                    logger.debug(f"STDERR: {stderr_line.strip()}")
                    
                    if 'time=' in stderr_line and expected_duration > 0:
                        try:
                            time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', stderr_line)
                            if time_match:
                                hours = int(time_match.group(1))
                                minutes = int(time_match.group(2))
                                seconds = int(time_match.group(3))
                                centiseconds = int(time_match.group(4))
                                
                                elapsed_time = hours * 3600 + minutes * 60 + seconds + centiseconds/100
                                stage_progress = min((elapsed_time / expected_duration) * 100, 100)
                                current_progress = int(stage_progress)
                                current_progress = min(current_progress, 99)
                                
                                if progress_callback:
                                    progress_callback(current_progress)
                                    
                        except:
                            pass
                
                if encode_id in self.active_encodes and self.active_encodes[encode_id].get('status') == 'stopped':
                    process.terminate()
                    logger.info(f"Process stopped by admin: {encode_id}")
                    return {'success': False, 'message': 'Encoding admin tarafından durduruldu'}
                
                if process.poll() is not None:
                    break

            process.wait(timeout=30)
            return_code = process.returncode
            
            logger.info(f"🔧 Process return code: {return_code}")
            
            if return_code != 0:
                error_output = stderr_output[-1000:] if stderr_output else "Bilinmeyen hata"
                logger.error(f"FFmpeg failed with code {return_code}")
                logger.error(f"STDERR: {error_output}")
                
                return {
                    'success': False,
                    'message': f'FFmpeg hatası (kod: {return_code}): {error_output}'
                }

            return {'success': True}

        except subprocess.TimeoutExpired:
            logger.error("Process timeout")
            return {'success': False, 'message': 'Process timeout'}
        except Exception as e:
            logger.exception(f"Process execution error: {str(e)}")
            return {'success': False, 'message': f'Process hatası: {str(e)}'}

    async def encode_single_pass(self, intro_path, episode_path, subtitle_path,
                                 output_filename, interaction, user_info="Unknown"):
        if not self.can_start_new_encode():
            active_count = self.get_active_encode_count()
            return False, f"❌ Maksimum encode limitine ulaşıldı! Aktif: {active_count}/{self.max_concurrent_encodes}"

        encode_id = f"{int(time.time())}_{user_info.replace(' ', '_')[:8]}"
        final_output = os.path.join(self.output_dir, output_filename)

        files_to_check = [
            ("Intro", intro_path),
            ("Episode", episode_path),
            ("Subtitle", subtitle_path)
        ]
        
        for name, path in files_to_check:
            if not os.path.exists(path):
                return False, f"{name} dosyası bulunamadı: {path}"

        self.add_active_encode(encode_id, user_info)

        progress_percent = 0

        def progress_callback(percent):
            nonlocal progress_percent
            progress_percent = percent

        progress_msg = None
        if interaction and discord:
            try:
                active_count = self.get_active_encode_count()
                embed = discord.Embed(
                    title="🚀 Video Encoding Başlatıldı",
                    description=(
                        f"🎬 Video işleniyor...\n"
                        f"📊 Aktif encode: {active_count}/{self.max_concurrent_encodes}\n"
                        f"⏳ İlerleme: {progress_percent}%\n"
                        f"🆔 ID: `{encode_id}`"
                    ),
                    color=0x3498DB
                )
                progress_msg = await interaction.followup.send(embed=embed)
            except Exception as e:
                self.logger.error(f"❌ Discord mesajı gönderilemedi: {e}")

        self.logger.info(f"🎬 Starting encoding: {encode_id} - {output_filename}")

        loop = asyncio.get_event_loop()
        encoding_task = loop.run_in_executor(
            self.executor,
            self._run_simple_encoding,
            intro_path,
            episode_path,
            final_output,
            subtitle_path,
            encode_id,
            progress_callback
        )

        start_time = time.time()
        last_update = 0

        while not encoding_task.done():
            current_time = time.time()
            
            if current_time - last_update > 45 and progress_msg and discord:
                try:
                    elapsed_minutes = int((current_time - start_time) / 60)
                    active_count = self.get_active_encode_count()

                    embed = discord.Embed(
                        title="⚡ Video Encoding Devam Ediyor",
                        description=(
                            f"🔥 İşleniyor...\n"
                            f"⏱️ Süre: {elapsed_minutes} dakika\n"
                            f"📊 Aktif: {active_count}/{self.max_concurrent_encodes}\n"
                            f"⏳ İlerleme: {progress_percent}%\n"
                            f"🆔 ID: `{encode_id}`"
                        ),
                        color=0xF39C12
                    )
                    await progress_msg.edit(embed=embed)
                    last_update = current_time
                except Exception:
                    last_update = current_time
                    
            await asyncio.sleep(15)

        result = await encoding_task
        
        self.remove_active_encode(encode_id)

        if result['success']:
            if progress_msg and discord:
                try:
                    embed = discord.Embed(
                        title="✅ Video Encoding Tamamlandı!",
                        description="🎉 Video başarıyla işlendi!",
                        color=0x27AE60
                    )
                    embed.add_field(name="📁 Dosya", value=f"`{output_filename}`", inline=True)
                    embed.add_field(name="📊 Boyut", value=f"`{result['file_size']/(1024*1024):.1f} MB`", inline=True)
                    embed.add_field(name="⚡ Süre", value=f"`{result['duration']/60:.1f} dakika`", inline=True)
                    embed.add_field(name="🆔 ID", value=f"`{encode_id}`", inline=True)

                    await progress_msg.edit(embed=embed)
                except Exception:
                    pass
            return True, result['message']
        else:
            if progress_msg and discord:
                try:
                    embed = discord.Embed(
                        title="❌ Video Encoding Başarısız!",
                        description=f"🚫 Hata: {result['message'][:500]}",
                        color=0xE74C3C
                    )
                    embed.add_field(name="🆔 ID", value=f"`{encode_id}`", inline=True)
                    await progress_msg.edit(embed=embed)
                except Exception:
                    pass
            return False, result['message']

    def cleanup_all_processes(self):
        logging.info("🧹 Cleaning up all processes")
        
        if psutil:
            terminated_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'ffmpeg' in proc.info['name'].lower():
                        proc.terminate()
                        terminated_count += 1
                    elif proc.info['cmdline'] and any('ffmpeg' in arg.lower() for arg in proc.info['cmdline']):
                        proc.terminate()
                        terminated_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            time.sleep(3)
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'ffmpeg' in proc.info['name'].lower():
                        if proc.is_running():
                            proc.kill()
                    elif proc.info['cmdline'] and any('ffmpeg' in arg.lower() for arg in proc.info['cmdline']):
                        if proc.is_running():
                            proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            logging.info(f"🧹 Terminated {terminated_count} FFmpeg processes")
        
        with self.encode_lock:
            self.active_encodes.clear()
        
        logging.info("🧹 All encoding processes cleaned up")


fast_encoder = FastVideoEncoder()

def test_encode(input_file):
    return fast_encoder.test_simple_encode(input_file)

async def encode_video(intro_path, episode_file, subtitle_path, output_file, interaction, user_info="Unknown"):
    episode_path = fast_encoder.find_video_file(episode_file)
    if not episode_path:
        return False, f"Episode dosyası bulunamadı: {episode_file}"
    
    if episode_file.startswith("downloads"):
        base_name = os.path.basename(episode_file)
    else:
        base_name = episode_file
    
    output_filename = os.path.splitext(base_name)[0] + ".mp4"
    
    return await fast_encoder.encode_single_pass(
        intro_path=intro_path,
        episode_path=episode_path, 
        subtitle_path=subtitle_path,
        output_filename=output_filename,
        interaction=interaction,
        user_info=user_info
    )

def check_ffmpeg_installed():
    try:
        FastVideoEncoder()
        return True
    except FileNotFoundError:
        return False

def get_active_encodes_info():
    active_encodes = fast_encoder.get_active_encodes_info()
    if not active_encodes:
        return f"📊 Aktif encode yok (0/{fast_encoder.max_concurrent_encodes})"
    
    info_lines = [f"📊 Aktif Encode'lar ({len(active_encodes)}/{fast_encoder.max_concurrent_encodes}):"]
    
    for encode_id, info in active_encodes.items():
        elapsed = int(time.time() - info['start_time'])
        elapsed_str = f"{elapsed//60}m {elapsed%60}s" if elapsed >= 60 else f"{elapsed}s"
        status_emoji = "🔴" if info['status'] == 'stopped' else "🟢"
        
        info_lines.append(f"{status_emoji} **{encode_id}** - {info['user']} - {elapsed_str}")
    
    return "\n".join(info_lines)

def stop_encode_by_id(encode_id):
    return fast_encoder.stop_encode(encode_id)

def cleanup_all_encodes():
    fast_encoder.cleanup_all_processes()
    logging.info("🧹 All encoding processes cleaned up")

def get_encode_count():
    return fast_encoder.get_active_encode_count()

def get_max_encode_limit():
    return fast_encoder.max_concurrent_encodes