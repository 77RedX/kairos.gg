import discord
from discord.ui import View, button

PAGE_SIZE = 10

def build_queue_embed(guild, current, queue, page):
    embed = discord.Embed(
        title=f"🎶 Music Queue — {guild.name}",
        color=discord.Color.blurple()
    )

    if current:
        embed.add_field(
            name="🎵 Now Playing",
            value=current,
            inline=False
        )
    else:
        embed.add_field(
            name="🎵 Now Playing",
            value="Nothing",
            inline=False
        )

    if not queue:
        embed.add_field(
            name="📭 Up Next",
            value="Queue is empty.",
            inline=False
        )
        return embed

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    chunk = queue[start:end]

    desc = "\n".join(
        f"`{i+start+1}.` {title}"
        for i, title in enumerate(chunk)
    )

    embed.add_field(
        name=f"📜 Up Next (Page {page})",
        value=desc,
        inline=False
    )

    total_pages = (len(queue) - 1) // PAGE_SIZE + 1
    embed.set_footer(text=f"Page {page}/{total_pages}")

    return embed


class QueueView(View):
    def __init__(self, interaction, queue_mgr, page=1):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.queue_mgr = queue_mgr
        self.page = page

    async def refresh(self):
        current, queue = self.queue_mgr.get_queue_snapshot(
            self.interaction.guild.id
        )
        embed = build_queue_embed(
            self.interaction.guild, current, queue, self.page
        )
        await self.interaction.edit_original_response(embed=embed, view=self)

    @button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, _):
        if interaction.user != self.interaction.user:
            return

        self.page = max(1, self.page - 1)
        await interaction.response.defer()
        await self.refresh()

    @button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _):
        if interaction.user != self.interaction.user:
            return

        _, queue = self.queue_mgr.get_queue_snapshot(
            interaction.guild.id
        )
        max_page = max(1, (len(queue) - 1) // PAGE_SIZE + 1)

        self.page = min(max_page, self.page + 1)
        await interaction.response.defer()
        await self.refresh()