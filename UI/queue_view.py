import discord
from discord.ui import View, button

PAGE_SIZE = 10

def build_queue_embed(guild, current, queue, page):
    embed = discord.Embed(
        title=f"💿 Music Queue • {guild.name}",
        color=0x2b2d31
    )

    if current:
        embed.add_field(
            name="🔊 Now Playing",
            value=f"**{current[1]}**",
            inline=False
        )
    else:
        embed.add_field(
            name="🔊 Now Playing",
            value="*Silence...*",
            inline=False
        )

    if not queue:
        embed.add_field(
            name="🎶 Up Next",
            value="*The queue is completely empty.*",
            inline=False
        )
        return embed

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = queue[start:end]

    # Clean formatting with source indicators
    desc = ""
    for i, item in enumerate(chunk):
        # Support both old format (title string) and new format ((title, source_tag) tuple)
        if isinstance(item, tuple):
            title, source_tag = item
        else:
            title, source_tag = item, "🎵"

        safe_title = title[:60] + "..." if len(title) > 60 else title
        desc += f"`{(i + start + 1):02d}.` {source_tag} {safe_title}\n"

    embed.add_field(
        name=f"⏳ Up Next",
        value=desc,
        inline=False
    )

    total_pages = max(1, (len(queue) - 1) // PAGE_SIZE + 1)
    embed.set_footer(text=f"Page {page}/{total_pages} • {len(queue)} tracks in queue • 🎵 = Queued  🤖 = Autoplay")

    return embed


class QueueView(View):
    def __init__(self, interaction, queue_mgr, page=1):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.queue_mgr = queue_mgr
        self.page = page

    async def refresh(self, current_interaction=None):
        current, queue = self.queue_mgr.get_queue_snapshot(
            self.interaction.guild.id
        )

        # Ensure page boundaries are respected if queue size shrinks
        max_page = max(1, (len(queue) - 1) // PAGE_SIZE + 1)
        self.page = min(self.page, max_page)

        embed = build_queue_embed(
            self.interaction.guild, current, queue, self.page
        )

        if current_interaction:
            await current_interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.interaction.edit_original_response(embed=embed, view=self)

    @button(label="◀", style=discord.ButtonStyle.primary)
    async def prev(self, interaction: discord.Interaction, _):
        if interaction.user != self.interaction.user:
            return await interaction.response.send_message("This isn't your menu!", ephemeral=True)

        self.page = max(1, self.page - 1)
        await self.refresh(interaction)

    @button(label="▶", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, _):
        if interaction.user != self.interaction.user:
            return await interaction.response.send_message("This isn't your menu!", ephemeral=True)

        _, queue = self.queue_mgr.get_queue_snapshot(interaction.guild.id)
        max_page = max(1, (len(queue) - 1) // PAGE_SIZE + 1)

        self.page = min(max_page, self.page + 1)
        await self.refresh(interaction)

    @button(label="🔀 Shuffle", style=discord.ButtonStyle.secondary)
    async def shuffle_btn(self, interaction: discord.Interaction, _):
        self.queue_mgr.shuffle(interaction.guild.id)
        await self.refresh(interaction)

    @button(label="🔄 Refresh", style=discord.ButtonStyle.secondary)
    async def refresh_btn(self, interaction: discord.Interaction, _):
        # Anyone can hit refresh to see the latest queue!
        await self.refresh(interaction)

    @button(label="🗑️ Clear", style=discord.ButtonStyle.danger)
    async def clear_btn(self, interaction: discord.Interaction, _):
        if interaction.user != self.interaction.user:
            return await interaction.response.send_message("This isn't your menu!", ephemeral=True)
        self.queue_mgr.clear_queue(interaction.guild.id)
        await self.refresh(interaction)