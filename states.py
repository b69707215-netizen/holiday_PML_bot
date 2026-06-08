from aiogram.fsm.state import State, StatesGroup

class Registration(StatesGroup):
    full_name = State()
    phone = State()
    role = State()

class VacationRequest(StatesGroup):
    start_date = State()
    end_date = State()
    confirm = State()

class OrderCreation(StatesGroup):
    order_type = State()
    select_template = State()
    fill_variables = State()
    confirm = State()

class BroadcastMessage(StatesGroup):
    message = State()
    confirm = State()

class SearchTeacher(StatesGroup):
    full_name = State()

class PMLBroadcast(StatesGroup):
    message_text = State()
    confirm = State()
