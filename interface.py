# импорты
import vk_api
from sqlalchemy import create_engine
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from config import community_token, access_token, db_url_object
from core import VkTools
import data_store
# отправка сообщений


class BotVK:
    def __init__(self, community_token, access_token, engine):
        self.vk = vk_api.VkApi(token=community_token)
        self.longpoll = VkLongPoll(self.vk)
        self.vk_tools = VkTools(access_token)
        self.engine = engine
        self.params = {}
        self.worksheets = []
        self.offset = 0
        print('\U0001F916 "VKinder" запущен!', sep='\n')

    def message_send(self, user_id, message, attachment=None):
        self.vk.method('messages.send',
                       {'user_id': user_id,
                        'message': message,
                        'attachment': attachment,
                        'random_id': get_random_id()}
                       )

    def event_handler(self):
        for event in self.longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                if not self.params:
                    # Логика для получения данных о пользователе
                    self.params = self.vk_tools.get_profile_info(event.user_id)

                if event.text.lower() == 'привет':
                    self.message_send(
                        event.user_id, f'Привет, {self.params["name"]}!\n')
                elif event.text.lower() == 'поиск':
                    # Проверка на наличие города в профиле
                    if self.params.get("city") is None:
                        self.message_send(
                            event.user_id, 'Укажите город, используя команду "город <название>"')
                        continue
                    elif self.params.get("year") is None:
                        self.message_send(
                            event.user_id, 'Укажите свой возраст, используя команду "возраст <число>"')
                        continue

                    # Логика для поиска анкет
                    self.message_send(
                        event.user_id, 'Начинаем поиск')
                    if not self.worksheets:
                        self.worksheets = self.vk_tools.search_worksheet(
                            self.params, self.offset)
                    if self.worksheets:
                        worksheet = self.worksheets.pop()
                        photos = self.vk_tools.get_photos(worksheet['id'])
                        photo_string = ''
                        for photo in photos:
                            photo_string += f'photo{photo["owner_id"]}_{photo["id"]},'
                    else:
                        self.worksheets = self.vk_tools.search_worksheet(
                            self.params, self.offset)
                    # worksheet = self.worksheets.pop()

                    # проверка анкеты в бд в соответствии с event.user_id'
                    # worksheet = None
                    new_worksheets = []
                    for worksheet in self.worksheets:
                        if not data_store.check_user(self.engine, event.user_id, worksheet['id']):
                            new_worksheets.append(worksheet)
                    self.worksheets = new_worksheets.copy()
                    worksheet = self.worksheets.pop(0)

                    photos = self.vk_tools.get_photos(worksheet['id'])
                    photo_string = ''
                    for photo in photos:
                        photo_string += f'photo{photo["owner_id"]}_{photo["id"]},'
                    self.offset += 30

                    self.message_send(
                        event.user_id,
                        f'имя: {worksheet["name"]} ссылка: vk.com/{worksheet["id"]}',
                        attachment=photo_string
                    )
                    # добавить анкету в бд в соответствии с event.user_id
                    data_store.add_user(self.engine, event.user_id, worksheet['id'])
                elif event.text.lower().startswith("город "):
                    city_name = ' '.join(event.text.lower().split()[1:])
                    city = self.vk_tools.get_city(city_name)
                    if city is None:
                        self.message_send(
                            event.user_id, 'Нет такого города. Повторите запрос')
                    else:
                        self.params['city'] = city['title']
                        self.message_send(
                            event.user_id, f'Город успешно установлен {city["title"]}')
                elif event.text.lower().startswith("возраст "):
                    age = event.text.lower().split()[1]
                    try:
                        age = int(age)
                    except ValueError:
                        self.message_send(
                            event.user_id, 'Введите число')
                        continue
                    if not 18 <= age <= 99:
                        self.message_send(
                            event.user_id, 'Ваш возраст должен быть от 18 до 80 лет')
                        continue
                    self.params['year'] = age
                    self.message_send(
                        event.user_id, 'Возраст успешно установлен')
                elif event.text.lower() == 'Пока':
                    self.message_send(
                        event.user_id, 'До новых встреч!!')
                else:
                    self.message_send(
                        event.user_id, 'Сформулируйте вопрос и повторите, пожалуйста.')


if __name__ == '__main__':
    engine = create_engine(db_url_object)
    data_store.Base.metadata.create_all(engine)

    bot_vk = BotVK(community_token, access_token, engine)
    bot_vk.event_handler()
