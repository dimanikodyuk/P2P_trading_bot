from aiogram import Bot
from aiogram.enums import ParseMode
from loguru import logger
from config.settings import settings
from datetime import datetime


class TelegramNotifier:
    def __init__(self):
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.chat_id = settings.TELEGRAM_CHAT_ID

    async def send_opportunity(self, opportunity: dict):
        """Send arbitrage opportunity notification with merchant details and amounts"""

        # Вибір емодзі залежно від прибутку
        if opportunity['net_profit'] > 1000:
            emoji = "🔴🔥"
        elif opportunity['net_profit'] > 500:
            emoji = "🟠💰"
        else:
            emoji = "🟢💵"

        # Розрахунок сум
        buy_amount_uah = opportunity['usdt_amount'] * opportunity['buy_price']
        sell_amount_uah = opportunity['usdt_amount'] * opportunity['sell_price']

        # Форматування діапазону
        if settings.MAX_DEAL_AMOUNT > 0:
            range_text = f"{settings.MIN_DEAL_AMOUNT:,.0f} - {settings.MAX_DEAL_AMOUNT:,.0f}"
        else:
            range_text = f"{settings.MIN_DEAL_AMOUNT:,.0f} +"

        message = f"""
{emoji} <b>ЗНАЙДЕНО АРБІТРАЖНУ МОЖЛИВІСТЬ</b> {emoji}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>ЦІНИ ТА СПРЕД</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Купівля USDT:</b> {opportunity['buy_price']:.2f} UAH
💵 <b>Продаж USDT:</b> {opportunity['sell_price']:.2f} UAH
📈 <b>Спред:</b> {opportunity['spread_percent']:.2f}%
⚡ <b>Спред (з прослизанням):</b> {opportunity.get('spread_with_slippage', 0):.2f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>СУМИ ДО СПЛАТИ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💸 <b>Потрібно заплатити:</b> <code>{buy_amount_uah:,.0f} грн</code>
   (за {opportunity['usdt_amount']:.0f} USDT за ціною {opportunity['buy_price']:.2f})

💵 <b>Отримаєте на рахунок:</b> <code>{sell_amount_uah:,.0f} грн</code>
   (за {opportunity['usdt_amount']:.0f} USDT за ціною {opportunity['sell_price']:.2f})

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 <b>РОЗРАХУНОК ПРИБУТКУ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💚 <b>Чистий прибуток:</b> <code>+{opportunity['net_profit']:.2f} грн</code>
📊 <b>ROI:</b> <code>{opportunity['roi_percent']:.2f}%</code>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚙️ <b>ПАРАМЕТРИ УГОДИ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💼 <b>Капітал:</b> {settings.STARTING_CAPITAL:.0f} грн
🎯 <b>Діапазон угоди:</b> {range_text} грн
🎯 <b>Прослизання:</b> {settings.SLIPPAGE_RESERVE_PERCENT}%
💸 <b>Комісія:</b> 0.1%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>МЕРЧАНТИ</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>🏦 ПРОДАВЕЦЬ USDT (купуємо у нього):</b>
• Ім'я: <code>{opportunity['buy_merchant']}</code>
• Рейтинг: {opportunity['buy_completion_rate']:.1f}%
• Угод: {opportunity['buy_order_count']}
• Ліміт: {opportunity['buy_min_amount']:.0f} - {opportunity['buy_max_amount']:.0f} UAH
• Доступно: {opportunity['buy_available']:.0f} USDT

<b>🏦 ПОКУПЕЦЬ USDT (продаємо йому):</b>
• Ім'я: <code>{opportunity['sell_merchant']}</code>
• Рейтинг: {opportunity['sell_completion_rate']:.1f}%
• Угод: {opportunity['sell_order_count']}
• Ліміт: {opportunity['sell_min_amount']:.0f} - {opportunity['sell_max_amount']:.0f} UAH
• Доступно: {opportunity['sell_available']:.0f} USDT

⏰ <i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>

⚠️ <i>Перевірте ліміти мерчанта перед угодою!</i>
        """

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            logger.success(
                f"Telegram notification sent: +{opportunity['net_profit']} UAH from {opportunity['buy_merchant']} -> {opportunity['sell_merchant']}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    async def send_status(self, status: str):
        """Send status message"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=f"🔄 <b>Статус бота:</b>\n{status}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send status: {e}")