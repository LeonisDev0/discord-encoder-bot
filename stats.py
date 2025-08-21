import json
import os
import time
import logging
import discord
import asyncio
import random
from datetime import datetime
from threading import Lock
from typing import Optional, Dict, Any

class ProfessionalBotStats:
    
    def __init__(self):
        self.stats_file = "logs/bot_stats.json"
        self.lock = Lock()
        
        self.stats = {
            "commands_processed": 0,
            "total_downloads": 0,
            "total_encodes": 0,
            "active_downloads": 0,
            "active_encodes": 0,
            "start_time": None,
            "connected_servers": 0,
            "total_users": 0,
            "download_success": 0,
            "download_failed": 0,
            "encode_success": 0,
            "encode_failed": 0,
            "session_start": None,
            "last_updated": None,
            "peak_concurrent_operations": 0,
            "total_data_processed_mb": 0,
            "average_encoding_time": 0,
            "system_health_score": 100,
            "daily_stats": {},
            "weekly_stats": {},
            "monthly_stats": {}
        }
        
        self.animated_emojis = {
            "loading": ["⏳", "⌛", "🔄", "⚡"],
            "success": ["✅", "🎉", "🌟", "💫"],
            "error": ["❌", "⚠️", "🚨", "💥"],
            "processing": ["🔥", "⚡", "🚀", "💨"],
            "stats": ["📊", "📈", "📉", "💹"]
        }
        
        self.professional_colors = {
            "primary": 0x2C3E50,
            "success": 0x27AE60,
            "warning": 0xF39C12,
            "danger": 0xE74C3C,
            "info": 0x3498DB,
            "purple": 0x9B59B6,
            "dark": 0x34495E,
            "gold": 0xFFD700,
            "cyan": 0x1ABC9C
        }
        
        os.makedirs("logs", exist_ok=True)
        self.load_stats()
        self.update_daily_stats()
        logging.info("🎯 ProfessionalBotStats initialized successfully")
    
    def load_stats(self):
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    loaded_stats = json.load(f)
                    for key, value in loaded_stats.items():
                        if key in self.stats:
                            self.stats[key] = value
                    logging.info("✅ Previous statistics loaded successfully")
        except Exception as e:
            logging.warning(f"⚠️ Could not load stats from file: {e}")
    
    def save_stats(self):
        try:
            with self.lock:
                self.stats["last_updated"] = time.time()
                with open(self.stats_file, "w", encoding="utf-8") as f:
                    json.dump(self.stats, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.warning(f"⚠️ Could not save stats to file: {e}")
    
    def update_daily_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.stats["daily_stats"]:
            self.stats["daily_stats"][today] = {
                "commands": 0,
                "downloads": 0,
                "encodes": 0,
                "data_processed": 0
            }
        
        if len(self.stats["daily_stats"]) > 30:
            oldest_date = min(self.stats["daily_stats"].keys())
            del self.stats["daily_stats"][oldest_date]
    
    def get_animated_emoji(self, category: str) -> str:
        return random.choice(self.animated_emojis.get(category, ["📊"]))
    
    def calculate_system_health(self) -> int:
        health_score = 100
        
        total_downloads = self.stats["download_success"] + self.stats["download_failed"]
        if total_downloads > 0:
            download_rate = self.stats["download_success"] / total_downloads
            health_score -= (1 - download_rate) * 30
        
        total_encodes = self.stats["encode_success"] + self.stats["encode_failed"]
        if total_encodes > 0:
            encode_rate = self.stats["encode_success"] / total_encodes
            health_score -= (1 - encode_rate) * 25
        
        if self.stats["active_downloads"] + self.stats["active_encodes"] > 10:
            health_score -= 15
        
        return max(0, min(100, int(health_score)))
    
    def get_health_status(self, score: int) -> str:
        if score >= 95:
            return f"🟢 **EXCELLENT** ({score}%)"
        elif score >= 85:
            return f"🔵 **VERY GOOD** ({score}%)"
        elif score >= 70:
            return f"🟡 **GOOD** ({score}%)"
        elif score >= 50:
            return f"🟠 **FAIR** ({score}%)"
        else:
            return f"🔴 **CRITICAL** ({score}%)"
    
    def get_trend_indicator(self, current: int, previous: int) -> str:
        if current > previous:
            return "📈 ↗️"
        elif current < previous:
            return "📉 ↘️"
        else:
            return "➡️ →"
    
    def set_start_time(self):
        self.stats["start_time"] = time.time()
        self.stats["session_start"] = datetime.now().isoformat()
        self.save_stats()
        logging.info("🚀 Bot start time recorded")
    
    def update_server_stats(self, servers: int, users: int):
        self.stats["connected_servers"] = servers
        self.stats["total_users"] = users
        self.save_stats()
    
    def increment_commands_processed(self):
        self.stats["commands_processed"] += 1
        today = datetime.now().strftime("%Y-%m-%d")
        if today in self.stats["daily_stats"]:
            self.stats["daily_stats"][today]["commands"] += 1
        self.save_stats()
    
    def increment_total_downloads(self):
        self.stats["total_downloads"] += 1
        today = datetime.now().strftime("%Y-%m-%d")
        if today in self.stats["daily_stats"]:
            self.stats["daily_stats"][today]["downloads"] += 1
        self.save_stats()
    
    def increment_active_downloads(self):
        self.stats["active_downloads"] += 1
        total_active = self.stats["active_downloads"] + self.stats["active_encodes"]
        if total_active > self.stats["peak_concurrent_operations"]:
            self.stats["peak_concurrent_operations"] = total_active
        self.save_stats()
    
    def decrement_active_downloads(self):
        self.stats["active_downloads"] = max(0, self.stats["active_downloads"] - 1)
        self.save_stats()
    
    def increment_download_success(self):
        self.stats["download_success"] += 1
        self.save_stats()
    
    def increment_download_failed(self):
        self.stats["download_failed"] += 1
        self.save_stats()
    
    def increment_total_encodes(self):
        self.stats["total_encodes"] += 1
        today = datetime.now().strftime("%Y-%m-%d")
        if today in self.stats["daily_stats"]:
            self.stats["daily_stats"][today]["encodes"] += 1
        self.save_stats()
    
    def increment_active_encodes(self):
        self.stats["active_encodes"] += 1
        total_active = self.stats["active_downloads"] + self.stats["active_encodes"]
        if total_active > self.stats["peak_concurrent_operations"]:
            self.stats["peak_concurrent_operations"] = total_active
        self.save_stats()
    
    def decrement_active_encodes(self):
        self.stats["active_encodes"] = max(0, self.stats["active_encodes"] - 1)
        self.save_stats()
    
    def increment_encode_success(self):
        self.stats["encode_success"] += 1
        self.save_stats()
    
    def increment_encode_failed(self):
        self.stats["encode_failed"] += 1
        self.save_stats()
    
    def get_uptime(self) -> str:
        if not self.stats["start_time"]:
            return "Unknown"
        
        uptime = time.time() - self.stats["start_time"]
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        minutes = int((uptime % 3600) // 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def get_success_rates(self) -> tuple:
        total_downloads = self.stats["download_success"] + self.stats["download_failed"]
        download_rate = (self.stats["download_success"] / total_downloads * 100) if total_downloads > 0 else 100
        
        total_encodes = self.stats["encode_success"] + self.stats["encode_failed"]
        encode_rate = (self.stats["encode_success"] / total_encodes * 100) if total_encodes > 0 else 100
        
        return download_rate, encode_rate
    
    def get_stats_embed(self) -> discord.Embed:
        download_rate, encode_rate = self.get_success_rates()
        health_score = self.calculate_system_health()
        
        if health_score >= 90:
            embed_color = self.professional_colors["success"]
        elif health_score >= 70:
            embed_color = self.professional_colors["warning"]
        else:
            embed_color = self.professional_colors["danger"]
        
        embed = discord.Embed(
            title=f"🎯 **LEONIS BOT** - Professional Dashboard",
            description=f"```ansi\n\u001b[1;36m█▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀█\n█           SYSTEM STATUS: ONLINE            █\n█▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄█\u001b[0m\n```",
            color=embed_color,
            timestamp=datetime.now()
        )
        
        health_status = self.get_health_status(health_score)
        system_info = f"""
        ```yaml
        System Health: {health_status}
        Uptime: {self.get_uptime()}
        Status: 🟢 OPERATIONAL
        Version: v4.0 PROFESSIONAL
        ```
        
        **📡 Network Stats**
        ```fix
        Servers: {self.stats['connected_servers']:,}
        Users: {self.stats['total_users']:,}
        Peak Concurrent Ops: {self.stats['peak_concurrent_operations']}
        ```
        """
        embed.add_field(name="🖥️ **SYSTEM OVERVIEW**", value=system_info, inline=False)
        
        activity_emoji = self.get_animated_emoji("processing")
        activity_info = f"""
        **{activity_emoji} Live Operations**
        ```diff
        + Active Downloads: {self.stats['active_downloads']}
        + Active Encodes: {self.stats['active_encodes']}
        + Commands Processed: {self.stats['commands_processed']:,}
        ```
        
        **📊 Session Overview**
        ```ini
        [Downloads] {self.stats['total_downloads']:,} total
        [Encodes] {self.stats['total_encodes']:,} total
        [Success Rate] {((self.stats['download_success'] + self.stats['encode_success']) / max(1, self.stats['total_downloads'] + self.stats['total_encodes']) * 100):.1f}%
        ```
        """
        embed.add_field(name="⚡ **REAL-TIME ACTIVITY**", value=activity_info, inline=True)
        
        download_perf_emoji = "🟢" if download_rate >= 90 else "🟡" if download_rate >= 70 else "🔴"
        encode_perf_emoji = "🟢" if encode_rate >= 90 else "🟡" if encode_rate >= 70 else "🔴"
        
        performance_info = f"""
        **📥 Download Performance**
        ```ansi
        \u001b[1;32m✓ Success: {self.stats['download_success']:,}\u001b[0m
        \u001b[1;31m✗ Failed: {self.stats['download_failed']:,}\u001b[0m
        \u001b[1;36m📊 Rate: {download_rate:.1f}%\u001b[0m {download_perf_emoji}
        ```
        
        **🎬 Encoding Performance**
        ```ansi
        \u001b[1;32m✓ Success: {self.stats['encode_success']:,}\u001b[0m
        \u001b[1;31m✗ Failed: {self.stats['encode_failed']:,}\u001b[0m
        \u001b[1;36m📊 Rate: {encode_rate:.1f}%\u001b[0m {encode_perf_emoji}
        ```
        """
        embed.add_field(name="🏆 **PERFORMANCE ANALYTICS**", value=performance_info, inline=True)
        
        today = datetime.now().strftime("%Y-%m-%d")
        today_stats = self.stats["daily_stats"].get(today, {})
        
        daily_info = f"""
        **📅 Today's Activity**
        ```yaml
        Commands: {today_stats.get('commands', 0):,}
        Downloads: {today_stats.get('downloads', 0):,}
        Encodes: {today_stats.get('encodes', 0):,}
        ```
        
        **🎯 Quick Stats**
        ```fix
        Total Operations: {(self.stats['total_downloads'] + self.stats['total_encodes']):,}
        Last Update: Just now
        Data Processed: {self.stats.get('total_data_processed_mb', 0):.1f} MB
        ```
        """
        embed.add_field(name="📈 **ANALYTICS DASHBOARD**", value=daily_info, inline=False)
        
        footer_emoji = self.get_animated_emoji("stats")
        embed.set_footer(
            text=f"{footer_emoji} Professional Bot System | Developed by LeonisDev0 | Last Update: {datetime.now().strftime('%H:%M:%S')}",
            icon_url="https://cdn.discordapp.com/emojis/852878543997227038.png"
        )
        
        if health_score >= 90:
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/852878543653650433.gif")
        elif health_score >= 70:
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/852878544165183530.gif")
        else:
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/852878544194674699.gif")
        
        return embed
    
    async def send_animated_stats(self, interaction: discord.Interaction):
        loading_emoji = self.get_animated_emoji("loading")
        loading_embed = discord.Embed(
            title=f"{loading_emoji} Loading Professional Dashboard...",
            description="```ansi\n\u001b[1;33m████████████████████████████████████████\u001b[0m\n```",
            color=self.professional_colors["info"]
        )
        
        await interaction.response.send_message(embed=loading_embed)
        await asyncio.sleep(1)
        
        return True
    
    def export_stats_report(self) -> Optional[str]:
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f"logs/professional_report_{timestamp}.json"
            
            download_rate, encode_rate = self.get_success_rates()
            health_score = self.calculate_system_health()
            
            report_data = {
                "report_info": {
                    "generated_at": datetime.now().isoformat(),
                    "report_version": "4.0 Professional",
                    "report_type": "Comprehensive System Analysis"
                },
                "bot_info": {
                    "name": "Leonis Professional Bot",
                    "version": "v4.0 PROFESSIONAL",
                    "uptime": self.get_uptime(),
                    "health_score": health_score,
                    "health_status": self.get_health_status(health_score)
                },
                "performance_metrics": {
                    "download_success_rate": download_rate,
                    "encode_success_rate": encode_rate,
                    "overall_efficiency": ((self.stats['download_success'] + self.stats['encode_success']) / max(1, self.stats['total_downloads'] + self.stats['total_encodes'])) * 100,
                    "peak_concurrent_operations": self.stats['peak_concurrent_operations']
                },
                "detailed_statistics": self.stats.copy(),
                "daily_breakdown": self.stats["daily_stats"]
            }
            
            with open(report_filename, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            
            logging.info(f"📋 Professional report exported: {report_filename}")
            return report_filename
        except Exception as e:
            logging.error(f"❌ Failed to export report: {e}")
            return None

BotStats = ProfessionalBotStats