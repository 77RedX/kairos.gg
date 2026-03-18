import discord

class RecommendView(discord.ui.View):
    def __init__(self, urls, play_callback):
        """
        urls: List of 5 YouTube URLs from the recommendation engine
        play_callback: The function in main.py that handles process_play_request
        """
        super().__init__(timeout=120) 
        self.urls = urls
        self.play_callback = play_callback

    @discord.ui.button(label="Queue All 5 Matches", style=discord.ButtonStyle.blurple, emoji="▶️")
    async def btn_queue_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Disable the button immediately so they can't double-click
        button.disabled = True
        button.label = "Adding to Queue..."
        button.style = discord.ButtonStyle.gray
        
        # 2. Edit the message to show the button is working
        await interaction.response.edit_message(view=self)
        
        # 3. Loop through the 5 URLs and fire the callback for each
        # This will trigger the "Processing..." logic in main.py 5 times
        for url in self.urls:
            try:
                await self.play_callback(interaction, url)
            except Exception as e:
                print(f"Failed to queue recommendation: {e}")

        # 4. Final UI update
        button.label = "All Added!"
        button.style = discord.ButtonStyle.success
        await interaction.edit_original_response(view=self)