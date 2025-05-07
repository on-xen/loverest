from aiogram.fsm.state import StatesGroup, State

class RestaurantCreation(StatesGroup):
    waiting_for_name = State()

class MenuItemForm(StatesGroup):
    name = State()
    photo = State()
    description = State()
    duration = State()
    payment_type = State()
    price = State()
    price_kisses = State()
    price_hugs = State()

class RestaurantEntry(StatesGroup):
    waiting_for_code = State()

class CustomStarsAmount(StatesGroup):
    waiting_for_amount = State()

class DonationComment(StatesGroup):
    waiting_for_comment = State()

class EditMenuItem(StatesGroup):
    waiting_for_name = State()
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_duration = State()
    waiting_for_payment_type = State()
    waiting_for_price_kisses = State()
    waiting_for_price_hugs = State()

class RestaurantSettings(StatesGroup):
    waiting_for_new_name = State()
    confirm_delete_restaurant = State()

class UserSearch(StatesGroup):
    waiting_for_query = State()

class BroadcastForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_text = State()
    waiting_for_photo = State()
    waiting_for_button = State()
    waiting_for_button_url = State()
    waiting_for_button_text = State()
    waiting_for_confirmation = State()
    waiting_for_schedule_date = State()
    waiting_for_schedule_time = State() 