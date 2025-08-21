import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import time
import logging
import json
import sys
from datetime import datetime
from downloader import download_magnet_with_progress, get_active_downloads_info
from encoder import encode_video, get_active_encodes_info, get_encode_count
from uploader import upload_video_to_drive, get_active_uploads_info, check_gdrive_available

ADMIN_IDS = [000000000000000000, 000000000000000000]

def setup_logging():
    os.makedirs("logs", exist_ok=True)
    log_filename = os.path.join("logs", f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(console_formatter)
    
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    logging.getLogger('discord').setLevel(logging.WARNING)
    return log_filename

def load_token():
    try:
        if os.path.exists("bot_token.txt"):
            with open("bot_token.txt", "r", encoding='utf-8') as f:
                return f.read().strip()
        else:
            logging.error("bot_token.txt dosyası bulunamadı!")
            return None
    except Exception as e:
        logging.error(f"Token yükleme hatası: {e}")
        return None

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

log_filename = setup_logging()

def create_progress_bar(progress: int, length: int = 20) -> str:
    """Create ASCII progress bar"""
    filled = int(length * progress / 100)
    empty = length - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {progress}%"

@bot.event
async def on_ready():
    try:
        logging.info(f"🤖 Bot aktif: {bot.user.name}")
        logging.info(f"📡 {len(bot.guilds)} sunucu, {len(bot.users)} kullanıcı")
        
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Professional Video Processing"
            ),
            status=discord.Status.online
        )
        
        try:
            synced = await tree.sync()
            logging.info(f"✅ {len(synced)} komut senkronize edildi")
        except Exception as sync_error:
            logging.error(f"❌ Sync hatası: {sync_error}")
        
        from uploader import check_gdrive_available
        gdrive_available = check_gdrive_available()
        logging.info(f"📦 Google Drive: {'✅ Aktif' if gdrive_available else '❌ Deaktif'}")
        
    except Exception as e:
        logging.error(f"❌ on_ready hatası: {e}")

@bot.event
async def on_app_command_error(interaction, error):
    logging.error(f"Slash komut hatası: {error}")
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ Hata oluştu: {str(error)[:100]}", ephemeral=True)
    except Exception as e:
        logging.error(f"Error response failed: {e}")

@tree.command(name="upload", description="Encode klasöründeki videoyu Google Drive'a yükler")
@app_commands.describe(video_name="Yüklenecek video adı (encode/ klasöründen aranacak)")
async def slash_upload(interaction: discord.Interaction, video_name: str):
    try:
        user = f"{interaction.user.display_name} ({interaction.user.id})"
        logging.info(f"📤 /upload komutu - {user} - {video_name}")

        if not check_gdrive_available():
            error_embed = discord.Embed(
                title="❌ Google Drive API Hatası",
                description="Google Drive API paketleri yüklü değil!",
                color=0xE74C3C
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        initial_embed = discord.Embed(
            title="📤 Google Drive Upload Başlatılıyor",
            description=f"**Video:** `{video_name}`\n⏳ Video aranıyor ve upload başlatılıyor...",
            color=0x4285F4,
            timestamp=datetime.now()
        )
        initial_embed.add_field(name="👤 Kullanıcı", value=interaction.user.mention, inline=True)
        initial_embed.add_field(name="📁 Arama Yeri", value="`encode/` klasörü", inline=True)
        initial_embed.set_footer(text="Google Drive Upload System")

        await interaction.response.send_message(embed=initial_embed)

        progress_message = None
        last_progress = -1

        async def progress_callback(progress: int, speed: str, eta: str):
            nonlocal progress_message, last_progress

            if progress - last_progress < 5 and progress < 100:
                return
            last_progress = progress

            progress_bar = create_progress_bar(progress)
            
            if progress < 30:
                color = 0xE74C3C
            elif progress < 70:
                color = 0xF39C12
            else:
                color = 0x27AE60

            progress_embed = discord.Embed(
                title="📤 Google Drive Upload Devam Ediyor",
                color=color,
                timestamp=datetime.now()
            )
            progress_embed.add_field(name="📁 Video", value=f"```{video_name}```", inline=False)
            progress_embed.add_field(name="📊 Progress", value=f"```{progress_bar}```", inline=False)
            progress_embed.add_field(name="🚀 Hız", value=speed, inline=True)
            progress_embed.add_field(name="⏱️ Kalan Süre", value=eta, inline=True)
            progress_embed.add_field(name="🔢 Yüzde", value=f"{progress}%", inline=True)
            progress_embed.add_field(name="👤 Kullanıcı", value=interaction.user.mention, inline=True)
            progress_embed.set_footer(text=f"Google Drive Upload • {progress}% Complete")

            try:
                if progress_message is None:
                    progress_message = await interaction.followup.send(embed=progress_embed)
                else:
                    await progress_message.edit(embed=progress_embed)
            except Exception as e:
                logging.warning(f"Progress update failed: {e}")

        success, result = await upload_video_to_drive(
            video_name=video_name,
            user_info=user,
            progress_callback=progress_callback
        )

        if success:
            success_embed = discord.Embed(
                title="✅ Google Drive Upload Tamamlandı!",
                description=f"**{result['file_name']}** başarıyla Google Drive'a yüklendi!",
                color=0x27AE60,
                timestamp=datetime.now()
            )

            file_size_mb = result['file_size'] / (1024 * 1024)
            file_size_text = f"{file_size_mb:.1f} MB"
            if file_size_mb > 1024:
                file_size_text = f"{file_size_mb / 1024:.2f} GB"

            success_embed.add_field(
                name="📁 Dosya Bilgileri",
                value=f"**Ad:** `{result['file_name']}`\n"
                      f"**Boyut:** {file_size_text}\n"
                      f"**ID:** `{result['file_id']}`",
                inline=False
            )

            upload_minutes = result['upload_time'] / 60
            time_text = f"{upload_minutes:.1f} dakika" if upload_minutes >= 1 else f"{result['upload_time']:.0f} saniye"

            success_embed.add_field(
                name="📊 Upload İstatistikleri",
                value=f"**Süre:** {time_text}\n"
                      f"**Ortalama Hız:** {result['average_speed']:.1f} MB/s\n"
                      f"**Durum:** ✅ Başarılı",
                inline=True
            )

            success_embed.add_field(name="👤 Upload Eden", value=interaction.user.mention, inline=True)
            success_embed.add_field(
                name="🔗 Erişim Linkleri",
                value=f"[📖 Görüntüle]({result['view_link']})\n[⬇️ İndir]({result['download_link']})",
                inline=False
            )
            success_embed.set_footer(text="Google Drive Upload System")

            try:
                if progress_message:
                    await progress_message.edit(embed=success_embed)
                else:
                    await interaction.followup.send(embed=success_embed)
            except:
                await interaction.followup.send(embed=success_embed)

            logging.info(f"✅ Upload başarılı - {user} - {video_name} - ID: {result['file_id']}")

        else:
            error_embed = discord.Embed(
                title="❌ Google Drive Upload Hatası",
                description=f"**Video:** `{video_name}`\n**Hata:** {result}",
                color=0xE74C3C,
                timestamp=datetime.now()
            )
            error_embed.add_field(name="👤 Kullanıcı", value=interaction.user.mention, inline=True)
            error_embed.add_field(name="📁 Video", value=video_name, inline=True)
            error_embed.set_footer(text="Google Drive Upload System")

            try:
                if progress_message:
                    await progress_message.edit(embed=error_embed)
                else:
                    await interaction.followup.send(embed=error_embed)
            except:
                await interaction.followup.send(embed=error_embed)

            logging.error(f"❌ Upload başarısız - {user} - {video_name}: {result}")

    except Exception as e:
        error_msg = f"Upload kritik hatası: {str(e)}"
        logging.error(f"❌ {error_msg}")

        try:
            await interaction.followup.send(f"❌ **Kritik Hata:** {str(e)[:200]}")
        except:
            pass

@tree.command(name="uploads", description="Aktif upload işlemlerini ve Google Drive durumunu gösterir")
async def slash_uploads(interaction: discord.Interaction):
    try:
        user = f"{interaction.user.display_name} ({interaction.user.id})"
        logging.info(f"📤 /uploads komutu - {user}")

        active_uploads_info = get_active_uploads_info()
        gdrive_status = "✅ Kullanılabilir" if check_gdrive_available() else "❌ API paketi yüklü değil"

        encode_dir = "encode"
        video_files = []
        total_size = 0

        if os.path.exists(encode_dir):
            try:
                video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm']
                for file in os.listdir(encode_dir):
                    file_path = os.path.join(encode_dir, file)
                    if os.path.isfile(file_path):
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in video_extensions:
                            file_size = os.path.getsize(file_path)
                            file_size_mb = file_size / (1024 * 1024)
                            file_time = os.path.getmtime(file_path)
                            file_date = datetime.fromtimestamp(file_time).strftime("%d.%m %H:%M")

                            video_files.append({
                                'name': file,
                                'size': file_size_mb,
                                'date': file_date,
                                'size_bytes': file_size
                            })
                            total_size += file_size

                video_files.sort(key=lambda x: x['size'], reverse=True)

            except Exception as e:
                logging.error(f"Encode directory read error: {e}")

        embed = discord.Embed(
            title="📤 Google Drive Upload Yöneticisi",
            color=0x4285F4,
            timestamp=datetime.now()
        )

        embed.add_field(
            name="☁️ Google Drive API",
            value=gdrive_status,
            inline=True
        )

        if active_uploads_info == "Aktif upload yok":
            embed.add_field(
                name="🔄 Aktif Upload'lar",
                value="🌙 Şu anda aktif upload bulunmuyor.",
                inline=False
            )
        else:
            active_info_short = (active_uploads_info[:800] + "...") if len(active_uploads_info) > 800 else active_uploads_info
            embed.add_field(
                name="🔄 Aktif Upload'lar",
                value=active_info_short,
                inline=False
            )

        if not video_files:
            embed.add_field(
                name="📁 Upload Edilebilir Videolar",
                value="📂 `encode/` klasöründe video bulunamadı.\n💡 `/encode` komutu ile video oluşturun.",
                inline=False
            )
        else:
            files_text = ""
            max_files_to_show = 10

            for i, file_info in enumerate(video_files[:max_files_to_show]):
                display_name = file_info['name']
                if len(display_name) > 35:
                    name_part = os.path.splitext(display_name)[0][:30]
                    ext_part = os.path.splitext(display_name)[1]
                    display_name = f"{name_part}...{ext_part}"

                size_text = f"{file_info['size']:.1f} MB"
                if file_info['size'] > 1024:
                    size_text = f"{file_info['size'] / 1024:.2f} GB"

                files_text += f"🎬 **{display_name}**\n"
                files_text += f"   📊 {size_text} • 📅 {file_info['date']}\n\n"

            if len(video_files) > max_files_to_show:
                files_text += f"*...ve {len(video_files) - max_files_to_show} video daha*"

            embed.add_field(
                name=f"📁 Upload Edilebilir Videolar ({len(video_files)} dosya)",
                value=files_text,
                inline=False
            )

            total_size_gb = total_size / (1024 * 1024 * 1024)
            size_text = f"{total_size_gb:.2f} GB" if total_size_gb >= 1 else f"{total_size / (1024 * 1024):.1f} MB"

            embed.add_field(
                name="📊 Özet Bilgiler",
                value=f"📁 **Toplam Video:** {len(video_files)}\n💾 **Toplam Boyut:** {size_text}",
                inline=True
            )

            if video_files:
                biggest_file = video_files[0]
                biggest_size = f"{biggest_file['size']:.1f} MB"
                if biggest_file['size'] > 1024:
                    biggest_size = f"{biggest_file['size'] / 1024:.2f} GB"

                embed.add_field(
                    name="🏆 En Büyük Video",
                    value=f"🎬 {biggest_file['name'][:25]}{'...' if len(biggest_file['name']) > 25 else ''}\n📊 {biggest_size}",
                    inline=True
                )

        embed.set_footer(text="Google Drive Upload Manager")

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        logging.error(f"Uploads command error: {e}")
        try:
            await interaction.response.send_message(
                "❌ Upload bilgileri alınırken hata oluştu!",
                ephemeral=True
            )
        except:
            pass

@tree.command(name="indir", description="Magnet veya torrent link ile video indir")
@app_commands.describe(
    magnet_link="İndirmek istediğiniz magnet link veya torrent link",
    filename="Kaydedilecek dosya adı (uzantısız)"
)
async def slash_indir(interaction: discord.Interaction, magnet_link: str, filename: str):
    try:
        user = f"{interaction.user.display_name} ({interaction.user.id})"
        logging.info(f"📥 /indir komutu - {user} - {filename}")
        
        initial_embed = discord.Embed(
            title="📥 İndirme Başlatılıyor",
            description=f"**Dosya:** `{filename}`\n⏳ İndirme işlemi başlatılıyor...",
            color=0x3498DB,
            timestamp=datetime.now()
        )
        initial_embed.add_field(name="👤 Kullanıcı", value=interaction.user.mention, inline=True)
        initial_embed.set_footer(text="Download Manager")
        
        await interaction.response.send_message(embed=initial_embed)
        
        success, message = await download_magnet_with_progress(
            magnet_link=magnet_link,
            custom_name=filename,
            output_dir="downloads",
            user_info=user,
            interaction=interaction
        )
        
        if success:
            logging.info(f"✅ İndirme başarılı - {user} - {filename}")
        else:
            logging.error(f"❌ İndirme başarısız - {user} - {filename}: {message}")
            
            error_embed = discord.Embed(
                title="❌ İndirme Hatası",
                description=f"**Hata:** {message[:1000]}",
                color=0xE74C3C,
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=error_embed)
    
    except Exception as e:
        error_msg = f"İndirme kritik hatası: {str(e)}"
        logging.error(f"❌ {error_msg}")
        
        try:
            await interaction.followup.send(f"❌ **Kritik Hata:** {str(e)[:500]}")
        except:
            pass

@tree.command(name="downloads", description="Aktif indirmeleri ve downloads klasöründeki dosyaları gösterir")
async def slash_downloads(interaction: discord.Interaction):
    try:
        user = f"{interaction.user.display_name} ({interaction.user.id})"
        logging.info(f"📥 /downloads komutu - {user}")
        
        active_downloads_info = get_active_downloads_info()
        
        downloads_dir = "downloads"
        downloaded_files = []
        total_size = 0
        
        if os.path.exists(downloads_dir):
            try:
                for file in os.listdir(downloads_dir):
                    file_path = os.path.join(downloads_dir, file)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        file_size_mb = file_size / (1024 * 1024)
                        
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv']:
                            emoji = "🎬"
                        elif file_ext in ['.mp3', '.wav', '.flac', '.aac']:
                            emoji = "🎵"
                        elif file_ext in ['.zip', '.rar', '.7z']:
                            emoji = "📦"
                        else:
                            emoji = "📄"
                        
                        file_time = os.path.getmtime(file_path)
                        file_date = datetime.fromtimestamp(file_time).strftime("%d.%m %H:%M")
                        
                        downloaded_files.append({
                            'name': file,
                            'size': file_size_mb,
                            'date': file_date,
                            'emoji': emoji
                        })
                        total_size += file_size
                
                downloaded_files.sort(key=lambda x: x['size'], reverse=True)
                
            except Exception as e:
                logging.error(f"Downloads directory read error: {e}")
        
        embed = discord.Embed(
            title="📥 İndirme Yöneticisi",
            color=0x3498DB,
            timestamp=datetime.now()
        )
        
        if active_downloads_info == "Aktif indirme yok":
            embed.add_field(
                name="🔄 Aktif İndirmeler",
                value="🌙 Şu anda aktif indirme bulunmuyor.",
                inline=False
            )
        else:
            active_info_short = active_downloads_info[:800] + "..." if len(active_downloads_info) > 800 else active_downloads_info
            embed.add_field(
                name="🔄 Aktif İndirmeler",
                value=active_info_short,
                inline=False
            )
        
        if not downloaded_files:
            embed.add_field(
                name="📁 Downloads Klasörü",
                value="📂 Henüz indirilmiş dosya bulunmuyor.\n💡 `/indir` komutu ile indirme başlatabilirsiniz.",
                inline=False
            )
        else:
            files_text = ""
            max_files_to_show = 15
            
            for i, file_info in enumerate(downloaded_files[:max_files_to_show]):
                display_name = file_info['name']
                if len(display_name) > 35:
                    name_part = os.path.splitext(display_name)[0][:30]
                    ext_part = os.path.splitext(display_name)[1]
                    display_name = f"{name_part}...{ext_part}"
                
                files_text += f"{file_info['emoji']} **{display_name}**\n"
                files_text += f"   📊 {file_info['size']:.1f} MB • 📅 {file_info['date']}\n\n"
            
            if len(downloaded_files) > max_files_to_show:
                files_text += f"*...ve {len(downloaded_files) - max_files_to_show} dosya daha*"
            
            embed.add_field(
                name=f"📁 Downloads Klasörü ({len(downloaded_files)} dosya)",
                value=files_text,
                inline=False
            )
            
            total_size_gb = total_size / (1024 * 1024 * 1024)
            size_text = f"{total_size_gb:.2f} GB" if total_size_gb >= 1 else f"{total_size / (1024 * 1024):.1f} MB"
            
            embed.add_field(
                name="📊 Özet Bilgiler",
                value=f"📁 **Toplam Dosya:** {len(downloaded_files)}\n💾 **Toplam Boyut:** {size_text}",
                inline=True
            )
            
            if downloaded_files:
                biggest_file = downloaded_files[0]
                embed.add_field(
                    name="🏆 En Büyük Dosya",
                    value=f"{biggest_file['emoji']} {biggest_file['name'][:25]}{'...' if len(biggest_file['name']) > 25 else ''}\n📊 {biggest_file['size']:.1f} MB",
                    inline=True
                )
        
        embed.set_footer(text="Download Manager")
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        error_msg = f"Downloads command error: {e}"
        logging.error(error_msg)
        try:
            await interaction.response.send_message(
                "❌ İndirme bilgileri alınırken hata oluştu!", 
                ephemeral=True
            )
        except:
            pass

@tree.command(name="encode", description="Intro, video ve altyazıdan MP4 oluşturur")
@app_commands.describe(
    intro="Intro video adı (Varsayılan intro.mp4)",
    episode="Ana bölüm videosu (.mkv uzantılı)",
    subtitle_file="Altyazı dosyası (.ass/.srt)",
    subtitle_name="Altyazı dosya adı (.ass uzantılı)"
)
async def slash_encode(
    interaction: discord.Interaction,
    intro: str,
    episode: str,
    subtitle_file: discord.Attachment,
    subtitle_name: str
):
    try:
        user = f"{interaction.user.display_name} ({interaction.user.id})"
        output_name = os.path.splitext(episode)[0] + ".mp4"
        logging.info(f"🎬 /encode komutu - {user} - {output_name}")
        
        initial_embed = discord.Embed(
            title="🎬 Encoding Başlatılıyor",
            description=f"**Çıktı:** `{output_name}`\n⏳ Video işleme başlatılıyor...",
            color=0x9B59B6,
            timestamp=datetime.now()
        )
        initial_embed.add_field(name="👤 Kullanıcı", value=interaction.user.mention, inline=True)
        initial_embed.set_footer(text="Video Encoder")
        
        await interaction.response.send_message(embed=initial_embed)
        
        if not subtitle_file.filename.lower().endswith(('.ass', '.srt')):
            error_embed = discord.Embed(
                title="❌ Dosya Formatı Hatası",
                description="Altyazı dosyası .ass veya .srt uzantılı olmalıdır!",
                color=0xE74C3C
            )
            await interaction.followup.send(embed=error_embed)
            return
        
        os.makedirs("subs", exist_ok=True)
        subtitle_path = os.path.join("subs", subtitle_name)
        
        try:
            await subtitle_file.save(subtitle_path)
            logging.info(f"📝 Altyazı kaydedildi: {subtitle_name}")
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Dosya Kaydetme Hatası",
                description=f"Altyazı dosyası kaydedilemedi: {str(e)[:500]}",
                color=0xE74C3C
            )
            await interaction.followup.send(embed=error_embed)
            return
        
        intro_path = os.path.join("downloads", intro)
        if not os.path.exists(intro_path):
            error_embed = discord.Embed(
                title="❌ Intro Dosyası Bulunamadı",
                description=f"Intro dosyası bulunamadı: `{intro_path}`",
                color=0xE74C3C
            )
            await interaction.followup.send(embed=error_embed)
            return
        
        logging.info(f"🛠️ Encoding başlatılıyor - {user} - {output_name}")
        success, result_message = await encode_video(
            intro_path, episode, subtitle_path, output_name, interaction
        )
        
        try:
            if os.path.exists(subtitle_path):
                os.remove(subtitle_path)
        except Exception as e:
            logging.debug(f"Subtitle cleanup error: {e}")
        
        if success:
            logging.info(f"✅ Encoding başarılı - {user} - {output_name}")
        else:
            logging.error(f"❌ Encoding başarısız - {user}: {result_message}")
            
            error_embed = discord.Embed(
                title="❌ Encoding Hatası",
                description=f"**Hata:** {result_message[:1000]}",
                color=0xE74C3C,
                timestamp=datetime.now()
            )
            await interaction.followup.send(embed=error_embed)
    
    except Exception as e:
        error_msg = f"Encoding kritik hatası: {str(e)}"
        logging.error(f"❌ {error_msg}")
        
        try:
            await interaction.followup.send(f"❌ **Kritik Hata:** {str(e)[:500]}")
        except:
            pass

@tree.command(name="encodestats", description="Aktif encode işlemleri ve encode klasörü bilgileri")
async def encode_stats_command(interaction: discord.Interaction):
    try:
        user = f"{interaction.user.display_name} ({interaction.user.id})"
        logging.info(f"📈 /encodestats komutu - {user}")
        
        active_encodes = get_active_encodes_info()
        active_count = get_encode_count()
        
        encode_dir = "encode"
        encoded_files = []
        total_encoded_size = 0
        
        if os.path.exists(encode_dir):
            try:
                for file in os.listdir(encode_dir):
                    if file.endswith('.mp4'):
                        file_path = os.path.join(encode_dir, file)
                        if os.path.isfile(file_path):
                            file_size = os.path.getsize(file_path)
                            file_time = os.path.getmtime(file_path)
                            file_date = datetime.fromtimestamp(file_time).strftime("%d.%m.%Y %H:%M")
                            
                            encoded_files.append({
                                'name': file,
                                'size': file_size / (1024 * 1024),
                                'date': file_date
                            })
                            total_encoded_size += file_size
                
                encoded_files.sort(key=lambda x: os.path.getmtime(os.path.join(encode_dir, x['name'])), reverse=True)
                
            except Exception as e:
                logging.error(f"Encode directory read error: {e}")
        
        embed = discord.Embed(
            title="📈 Encode İstatistikleri",
            color=0x9B59B6,
            timestamp=datetime.now()
        )
        
        if active_count > 0:
            embed.add_field(
                name="🔄 Aktif Encode'lar",
                value=f"```\n{active_encodes}\n```",
                inline=False
            )
        else:
            embed.add_field(
                name="🔄 Aktif Encode'lar",
                value="🌙 Şu anda aktif encode bulunmuyor.",
                inline=False
            )
        
        embed.add_field(
            name="🖥️ Sistem Durumu",
            value=f"**Aktif İşlem:** {active_count}\n**FFmpeg:** Aktif\n**Encoder:** Professional",
            inline=True
        )
        
        if encoded_files:
            total_gb = total_encoded_size / (1024 * 1024 * 1024)
            
            embed.add_field(
                name="📊 Encode Edilen Dosyalar",
                value=f"**Toplam:** {len(encoded_files)} dosya\n"
                      f"**Boyut:** {total_gb:.2f} GB\n"
                      f"**Klasör:** `encode/`",
                inline=True
            )
            
            recent_files_text = ""
            for i, file_info in enumerate(encoded_files[:5]):
                display_name = file_info['name']
                if len(display_name) > 30:
                    display_name = display_name[:27] + "..."
                
                recent_files_text += f"🎬 **{display_name}**\n"
                recent_files_text += f"   📊 {file_info['size']:.1f} MB • 📅 {file_info['date']}\n\n"
            
            if len(encoded_files) > 5:
                recent_files_text += f"*...ve {len(encoded_files) - 5} dosya daha*"
            
            embed.add_field(
                name="🕒 Son Encode'lanan Dosyalar",
                value=recent_files_text if recent_files_text else "Henüz encode edilmiş dosya yok.",
                inline=False
            )
        else:
            embed.add_field(
                name="📊 Encode Edilen Dosyalar",
                value="📂 Henüz encode edilmiş dosya bulunmuyor.\n💡 `/encode` komutu ile encode başlatabilirsiniz.",
                inline=False
            )
        
        embed.set_footer(text="Video Encoder Statistics")
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Hata",
            description=f"Encode istatistikleri alınırken hata oluştu:\n```{str(e)}```",
            color=0xE74C3C
        )
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

def main():
    try:
        if sys.platform == "win32":
            os.system("chcp 65001")
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='ignore')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8', errors='ignore')
        
        token = load_token()
        if not token:
            print("❌ Bot token bulunamadı! Lütfen bot_token.txt dosyasını oluşturun.")
            return
        
        print("🚀 Professional Video Bot başlatılıyor...")
        print(f"📝 Log dosyası: {log_filename}")
        print(f"👑 Admin sayısı: {len(ADMIN_IDS)}")
        logging.info("🚀 Bot başlatılıyor...")
        
        bot.run(token, log_handler=None)
        
    except discord.LoginFailure:
        logging.error("❌ Geçersiz bot token!")
        print("❌ Geçersiz bot token!")
    except KeyboardInterrupt:
        logging.info("👋 Bot kapatılıyor...")
        print("👋 Bot kapatılıyor...")
    except Exception as e:
        logging.error(f"🚨 Bot başlatma hatası: {e}")
        print(f"❌ Bot başlatma hatası: {e}")

if __name__ == "__main__":
    main()