"""Custom emoji icons on inline buttons (Bot API 9.4 `icon_custom_emoji_id`).

Icons live in the adaptive emoji set t.me/addemoji/pipun_icons_by_ppntestbot.
Buttons are matched by text (the locale value of the key), so every button with
that text gets the icon, wherever it is built. Unknown texts are left alone.
"""
from aiogram.client.session.middlewares.base import BaseRequestMiddleware

ICONS = {  # locale key -> custom_emoji_id
    "menu_subscribe_inline": "5458677990382677879",        # buy
    "menu_my_subscription_inline": "5460929596922832051",  # subscription (key)
    "menu_referral_inline": "5458917619493023300",         # referral (paper plane)
    "referral_share_message_button": "5458917619493023300",
    "menu_server_status_button": "5458738768464884652",    # servers
    "menu_support_button": "5458708226952440112",          # support
    "menu_terms_button": "5458450417245532282",            # documents
    "connect_button": "5458511371421397481",               # connect
    "renew_subscription_button": "5458396025779694464",    # extend
    "renew_short_button": "5458396025779694464",
    "pay_with_platega_button": "5458436832263976001",      # SBP QR
    "pay_with_platega_card_button": "5458626094292837850", # card
    "pay_button": "5458920681804703553",                   # pay
    "back_to_main_menu_button": "5458437283235538631",     # back
    "back_to_payment_methods_button": "5458437283235538631",
    "back_to_autopay_method_choice_button": "5458437283235538631",
    "cancel_button": "5461117720785365933",                # cancel
}


class ButtonIconsMiddleware(BaseRequestMiddleware):
    def __init__(self, i18n, lang: str):
        self.by_text = {i18n.gettext(lang, k): v for k, v in ICONS.items()}

    async def __call__(self, make_request, bot, method):
        markup = getattr(method, "reply_markup", None)
        for row in getattr(markup, "inline_keyboard", None) or ():
            for button in row:
                icon = self.by_text.get(button.text)
                if icon and not getattr(button, "icon_custom_emoji_id", None):
                    button.icon_custom_emoji_id = icon
        return await make_request(bot, method)
