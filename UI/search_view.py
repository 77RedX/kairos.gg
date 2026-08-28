import discord

class SearchDropdown(discord.ui.Select):
    def __init__(self, results, play_callback):
        self.play_callback = play_callback
        options = []
        
        for i, res in enumerate(results):
            if not res: 
                continue
            
            title = res.get('title', 'Unknown Title')[:95] 
            uploader = res.get('uploader', 'Unknown Artist')[:80]

            # Format duration if available
            duration = res.get('duration')
            if duration:
                mins, secs = divmod(int(duration), 60)
                dur_str = f" • {mins}:{secs:02d}"
            else:
                dur_str = ""
            
            url = res.get('url')
            if url and not url.startswith('http'):
                url = f"https://www.youtube.com/watch?v={url}"
            elif not url:
                url = f"https://www.youtube.com/watch?v={res.get('id')}"

            options.append(discord.SelectOption(
                label=f"{i+1}. {title}",
                description=f"By {uploader}{dur_str}"[:100],
                value=url
            ))

        super().__init__(
            placeholder="Choose a track to play...", 
            min_values=1, 
            max_values=1, 
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_url = self.values[0]
        
        await interaction.response.edit_message(
            content=f"🎵 **Selected!** Adding to the queue...", 
            view=None
        )
        
        await self.play_callback(interaction, selected_url)

class SearchMenu(discord.ui.View):
    def __init__(self, results, play_callback):
        super().__init__(timeout=60)
        self.add_item(SearchDropdown(results, play_callback))