import time
import discord
from discord.ui import View, Button

def format_uptime(seconds: float) -> str:
    mins, sec = divmod(int(seconds), 60)
    hrs, mins = divmod(mins, 60)
    days, hrs = divmod(hrs, 24)

    if days > 0:
        return f"{days}d {hrs}h {mins}m"
    if hrs > 0:
        return f"{hrs}h {mins}m"
    return f"{mins}m {sec}s"


def build_info_embed(interaction, page, bot, start_time):
    uptime_seconds = time.time() - start_time
    uptime = format_uptime(uptime_seconds)

    vc = interaction.guild.voice_client
    in_vc = "Yes" if vc and vc.is_connected() else "No"

    commands_list = sorted(
        [cmd.name for cmd in bot.tree.get_commands()]
    )

    PER_PAGE = 5
    total_pages = max(1, (len(commands_list) + PER_PAGE - 1) // PER_PAGE)

    start = (page - 1) * PER_PAGE
    end = start + PER_PAGE
    page_cmds = commands_list[start:end]

    embed = discord.Embed(
        title="🤖 Bot Info",
        color=discord.Color.blurple()
    )

    embed.add_field(name="⏱ Uptime", value=uptime, inline=True)
    embed.add_field(name="🎧 In Voice Channel", value=in_vc, inline=True)

    embed.add_field(
        name=f"📜 Commands (Page {page}/{total_pages})",
        value="\n".join(f"`/{c}`" for c in page_cmds),
        inline=False
    )

    return embed, total_pages


class InfoView(View):
    def __init__(self, interaction, bot, start_time, page=1):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.bot = bot
        self.start_time = start_time
        self.page = page

        _, self.total_pages = build_info_embed(
            interaction, page, bot, start_time
        )
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()

        if self.page > 1:
            self.add_item(
                Button(label="◀ Prev", style=discord.ButtonStyle.secondary)
            )
        if self.page < self.total_pages:
            self.add_item(
                Button(label="Next ▶", style=discord.ButtonStyle.secondary)
            )

    async def interaction_check(self, interaction):
        return interaction.user == self.interaction.user

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction, button):
        self.page -= 1
        embed, _ = build_info_embed(
            self.interaction, self.page, self.bot, self.start_time
        )
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction, button):
        self.page += 1
        embed, _ = build_info_embed(
            self.interaction, self.page, self.bot, self.start_time
        )
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
