import time
import discord
from discord.ui import View, button

def build_info_embed(interaction, page, bot, start_time):
    vc = interaction.guild.voice_client
    in_vc = "Connected" if vc and vc.is_connected() else "Disconnected"

    # Use Discord's native relative timestamp (automatically updates in UI!)
    uptime_str = f"<t:{int(start_time)}:R>"

    commands_list = sorted(cmd.name for cmd in bot.tree.get_commands())
    PER_PAGE = 6 
    total_pages = max(1, (len(commands_list) + PER_PAGE - 1) // PER_PAGE)
    page = max(1, min(page, total_pages))

    start = (page - 1) * PER_PAGE
    page_cmds = commands_list[start:start + PER_PAGE]

    # 0x2b2d31 is the invisible embed color for Discord dark mode
    embed = discord.Embed(
        title="✨ KaiROS System Info",
        color=0x2b2d31 
    )
    
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.add_field(name="⏱️ Uptime", value=uptime_str, inline=True)
    embed.add_field(name="🎙️ Voice Status", value=in_vc, inline=True)

    # Format commands beautifully
    cmd_strings = [f"**`/{c}`**" for c in page_cmds]
    embed.add_field(
        name=f"🛠️ Commands (Page {page}/{total_pages})",
        value="\n".join(cmd_strings) or "No commands available.",
        inline=False
    )
    
    embed.set_footer(
        text=f"Requested by {interaction.user.display_name}", 
        icon_url=interaction.user.display_avatar.url
    )

    return embed, total_pages


class InfoView(View):
    def __init__(self, interaction, bot, start_time, page=1):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.bot = bot
        self.start_time = start_time
        self.page = page

        _, self.total_pages = build_info_embed(
            interaction, page, bot, start_time
        )
        self._update_button_state()

    async def interaction_check(self, interaction):
        return interaction.user == self.interaction.user

    def _update_button_state(self):
        self.prev.disabled = self.page <= 1
        self.next.disabled = self.page >= self.total_pages

    @button(label="◀ Prev", style=discord.ButtonStyle.primary)
    async def prev(self, interaction: discord.Interaction, btn):
        self.page -= 1
        embed, _ = build_info_embed(
            self.interaction, self.page, self.bot, self.start_time
        )
        self._update_button_state()
        await interaction.response.edit_message(embed=embed, view=self)

    @button(label="Next ▶", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, btn):
        self.page += 1
        embed, _ = build_info_embed(
            self.interaction, self.page, self.bot, self.start_time
        )
        self._update_button_state()
        await interaction.response.edit_message(embed=embed, view=self)
        
    @button(label="🗑️", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, btn):
        await interaction.message.delete()