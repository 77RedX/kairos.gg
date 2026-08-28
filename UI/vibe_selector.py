import discord
from database.database import get_track_by_vibe

class VibeSelector(discord.ui.View):
    def __init__(self, play_callback):
        super().__init__(timeout=60) # Buttons vanish after 60 seconds
        self.play_callback = play_callback # This links back to your queuemgr in main.py

    async def process_selection(self, interaction: discord.Interaction, vibe: str, color: discord.Color):
        tracks = get_track_by_vibe(vibe)
        
        if not tracks:
            await interaction.response.send_message("I don't have enough songs in this vibe yet!", ephemeral=True)
            return
            
        # DB returns up to 3 candidates; queue only the first — qmgr handles failures.
        title, url, v, a = tracks[0]
        
        # 1. Update the UI to show the chosen song and remove the buttons
        embed = discord.Embed(
            title="🎧 Kicking things off!",
            description=f"Starting the queue with:\n**[{title}]({url})**\n*(V: {v:.2f} | A: {a:.2f})*",
            color=color
        )
        # Show fallback count if additional candidates were returned
        if len(tracks) > 1:
            embed.set_footer(text=f"{len(tracks)-1} fallback tracks ready if this one fails.")
            
        await interaction.response.edit_message(content=None, embed=embed, view=None)
        
        # 2. Trigger the actual playback back in main.py. We'll queue the first track.
        await self.play_callback(interaction, url)

    @discord.ui.button(label="Hype & Upbeat", style=discord.ButtonStyle.success, emoji="🔥")
    async def btn_hype(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_selection(interaction, "hype", discord.Color.green())

    @discord.ui.button(label="Chill & Relaxing", style=discord.ButtonStyle.primary, emoji="🍃")
    async def btn_chill(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_selection(interaction, "chill", discord.Color.blue())

    @discord.ui.button(label="Intense & Aggressive", style=discord.ButtonStyle.danger, emoji="💥")
    async def btn_intense(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_selection(interaction, "intense", discord.Color.red())

    @discord.ui.button(label="Dark & Melancholic", style=discord.ButtonStyle.secondary, emoji="🌧️")
    async def btn_sad(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_selection(interaction, "sad", discord.Color.dark_grey())