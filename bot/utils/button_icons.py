"""Custom emoji icons on inline buttons (Bot API 9.4 `icon_custom_emoji_id`).

Icons live in the adaptive emoji set t.me/addemoji/pipun_icons_by_ppntestbot.
Buttons are matched by text (the locale value of the key), so every button with
that text gets the icon, wherever it is built. Unknown texts are left alone.
"""
from aiogram.client.session.middlewares.base import BaseRequestMiddleware

ICONS = {  # locale key -> custom_emoji_id
    "menu_subscribe_inline": "5460847958184475262",        # buy, pink: separate non-adaptive set pipun_accent_by_ppntestbot
    "menu_my_subscription_inline": "5458836753848771681",  # subscription (key)
    "menu_referral_inline": "5460861165208907427",         # referral (gift)
    "referral_share_message_button": "5458728125535922865",  # paper plane
    "menu_server_status_button": "5458446955501889989",    # servers
    "menu_support_button": "5461163990468045498",          # support
    "menu_terms_button": "5458474516307028687",            # documents
    "connect_button": "5458530200558026384",               # connect
    "renew_subscription_button": "5458690639061366368",    # extend
    "renew_short_button": "5458690639061366368",
    "pay_with_platega_sub_button": "5458690639061366368",  # extend
    "autopay_subscribe_button": "5458690639061366368",
    "autopay_disable_button": "5458694491647028850",  # cancel
    "pay_with_platega_button": "5458392473841737822",      # SBP QR
    "pay_with_platega_card_button": "5461168006262464113", # card
    "pay_button": "5458768128861317632",                   # pay
    "back_to_main_menu_button": "5458389789487177592",     # back
    "back_to_payment_methods_button": "5458389789487177592",
    "back_to_autopay_method_choice_button": "5458389789487177592",
    "cancel_button": "5458694491647028850",                # cancel
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
