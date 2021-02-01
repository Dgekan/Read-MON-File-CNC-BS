#!/usr/bin/python3
# -*- coding: utf-8 -*-

#  ------------------------Коды ошибок---------------------
#  8 - Ошибка контрольной суммы сообщения
#
#  --------------------------------------------------------
#
#
#
#

import copy
import datetime
import functools
import operator
# from logging import error
import os
import pymysql
import struct
import time
# from pymysql.cursors import DictCursor
from contextlib import closing

import configobj

buf_list = []  # В этот лист считываем весь фаил
list_header = []  # Заголовок файла
proc_info = []  # Основная структура сюда записываем индекс сообщений
show_val_list = []  # Лист в котором хранится текущее состояние станка
sql_list = []  # Лист для записи в sqlite
mysql_list = []  # Лист для записи в mysql
for i in range(41):  # Генерируем основную структуру
    show_val_list.append(i)

index: int = 0  # Основной индекс
name_file_mon: str = ""  # Имя бинарного файла
database_sqlite: str = ""  # Имя базы данных sqlite
catalog: str = ""  # Каталог в котором лежит бинарный фаил
WORK_MODE_ST = {1: "MDI", 2: "AUTO", 3: "STEP", 4: "MANU", 5: "MANJ", 6: "PROF", 7: "HOME", 8: "RESET",
                0: "0"}  # Состаянние станка
type_event: int = 0  # Тип сообщения от 1 до 41 в структуре: show_val_list
date = ""  # Текущая дата из бинарного файла
host = ""  # Адрес база данных mysql
user = ""  # Пользовател базы данных mysql
password = ""  # Пароль базы данных mysql
db = ""  # Имя базы данных mysql
count_millis: int = 0  # Счетчик  милисикунд дпя отправки пакета в mysql
timer_sql = time.monotonic()  # Таймер 5 сек дпя отправки пакета в mysql
timer_sql_mon = time.monotonic()
counter: int = 0  # Счетчик сообщений дпя отправки пакета в mysql


def read_config():
    """
    Читаем фаил конфиг "config.ini"  
    """
    global catalog
    global database_sqlite
    global host
    global user
    global password
    global db
    ini_file = "config.ini"
    config = configobj.ConfigObj(ini_file)
    if not config.file_error:
        catalog = config["catalog"]
        database_sqlite = config["database_sqlite"]
        host = config['host']
        user = config['user']
        password = config['password']
        db = config['db']
    else:
        print("Не удалось открыть файл config.ini")
        exit(2)


def open_file_current() -> str:
    """
    Читаем фаил current.inf
    """
    global catalog, name_file_mon
    if os.path.exists(catalog + "current.inf"):
        file = open(catalog + "current.inf", "r")
        name_file_mon = file.read(18)
        file.close()
        return name_file_mon
    else:
        print("Не удалось открыть файл current.inf")
        exit(2)


def read_file(file_name: str):
    """
    open_file(имя_файла)

    Пример file_name= 20020104093446.mon \n
    Читаем весь фаил .mon указанный в файле  current.inf \n
    в лист buf_list=[]
    """
    global catalog

    if os.path.exists(catalog + file_name):

        file = open(catalog + file_name, "rb")

        while True:
            char = file.read(1)
            if not char:
                break
            buf_list.append(char)
        file.close()
    else:
        print("Не удалось открыть файл ", file_name, " указанный в current.inf ")
        exit(2)


def get_val_from_buf(length: int, kind: str, on_index: bool = True):
    """
    -> int, -> str, ->float, ->time \n
    length -- Количество байт (длина) \n
    kind ---  Тип к которому мы приводим \n
    on_index ---  разрешаем увиличивать индекс, по умолчанию = True

    """
    global index
    a = b''
    index_min = index
    index_max = index + length
    if on_index:
        index += length

    if kind == "int":
        for i1 in range(index_min, index_max):
            a += buf_list[i1]
        return int.from_bytes(a, byteorder='little', signed=False)

    elif kind == "str":
        list1 = []
        for i2 in range(index_min, index_max):
            if buf_list[i2] != b'\x00': 
                list1.append(buf_list[i2].decode('cp866'))
        return ''.join(str(x) for x in list1)

    elif kind == "time":
        for i3 in range(index_min, index_max):
            a += buf_list[i3]
        time_ = int.from_bytes(a, byteorder='little', signed=False)
        hours = time_ // (3600 * 1000 * 10)
        minutes = (time_ - hours * 3600 * 1000 * 10) // (60 * 1000 * 10)
        seconds = (time_ - hours * 3600 * 1000 * 10 - minutes * 60 * 1000 * 10) // (1000 * 10)
        milliseconds = (time_ - hours * 3600 * 1000 * 10 - minutes * 60 * 1000 * 10 - seconds * 1000 * 10) // 10
        return str(datetime.time(hours, minutes, seconds, milliseconds))

    elif kind == "float":
        a = b''
        for i4 in range(index_min, index_max):
            a += buf_list[i4]
        return float("{0:.4f}".format(functools.reduce(operator.add, (struct.unpack('f', a)))))


def load_header():
    """
    Читаем заголовок файла и  записываем его в две структуры
    """
    global date
    list_header.clear()
    list_header.append(get_val_from_buf(4, "str"))  #
    list_header.append(get_val_from_buf(4, "str"))  #
    list_header.append(get_val_from_buf(4, "int"))  #
    list_header.append(get_val_from_buf(25, "str"))  #
    list_header.append(get_val_from_buf(25, "str"))  #
    list_header.append(get_val_from_buf(1, "int"))  #
    software_version_len = get_val_from_buf(1, "int")
    list_header.append(get_val_from_buf(software_version_len, "str"))  #
    list_header.append(get_val_from_buf(25, "str"))  #
    list_header.append(get_val_from_buf(2, "int"))  #
    list_header.append(get_val_from_buf(4, "int"))  #
    list_header.append(get_val_from_buf(2, "int"))  #
    list_header.append(get_val_from_buf(2, "int"))  #
    list_header.append(get_val_from_buf(2, "int"))  #
    list_header.append(get_val_from_buf(1, "int"))  #
    list_header.append(get_val_from_buf(12, "int"))  #
    num_proc = get_val_from_buf(1, "int")

    for proc in range(num_proc):
        kol_event = get_val_from_buf(2, "int")

        structure_kol_event = []

        for event in range(kol_event):
            structure_event = [get_val_from_buf(2, "int"), get_val_from_buf(4, "int"), get_val_from_buf(4, "int"),
                               get_val_from_buf(1, "int")]
            structure_kol_event.append(structure_event)

        proc_info.append(structure_kol_event)


def get_event(event: int, time_event: int) -> int:
    """
    Заполняем  лист show_val_list вложенным листом event_list \n
    Пример - event_list = [09:12:49.0063, SPINDLE SPEED:, 1350.0]
    """
    global index
    global date
    event_list = [str(time_event)]

    if event == 1:
        event_list.append("NO EVENT")
        show_val_list[1] = event_list
        return 0
    if event == 2:
        event_list.append("SYSTEM START: ")
        event_list.append(get_val_from_buf(2, 'int'))
        event_list.append(get_val_from_buf(2, 'int'))
        event_list.append(get_val_from_buf(2, 'int'))
        event_list.append(get_val_from_buf(4, 'int'))
        system_start_data_character_files_num = get_val_from_buf(1, 'int')
        for i5 in range(system_start_data_character_files_num):
            len_ = get_val_from_buf(1, 'int')
            event_list.append(get_val_from_buf(len_, 'str'))
            len_ = get_val_from_buf(1, 'int')
            event_list.append(get_val_from_buf(len_, 'str'))
            len_ = get_val_from_buf(1, 'int')
            event_list.append(get_val_from_buf(len_, 'str'))
        show_val_list[2] = event_list
        date = datetime.date(show_val_list[2][2], show_val_list[2][3], show_val_list[2][4])
        return 0
    if event == 3:
        event_list.append("NEW DATE: ")
        event_list.append(get_val_from_buf(2, 'int'))
        event_list.append(get_val_from_buf(2, 'int'))
        event_list.append(get_val_from_buf(2, 'int'))
        show_val_list[3] = event_list
        date = datetime.date(show_val_list[3][2], show_val_list[3][3], show_val_list[3][4])
        return 0
    if event == 4:
        event_list.append(list_header[7])
        event_list.append("WORK MODE: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[4] = [event_list[0], event_list[1], event_list[2], WORK_MODE_ST[int(event_list[3])]]
        mysql(event_list)
        return 0
    if event == 5:
        event_list.append(list_header[7])
        event_list.append("FEED: ")
        event_list.append(str(get_val_from_buf(4, 'float')))
        show_val_list[5] = event_list
        mysql(event_list)
        return 0
    if event == 6:
        event_list.append(list_header[7])
        event_list.append("SPINDLE SPEED: ")
        event_list.append(str(get_val_from_buf(4, 'float')))
        show_val_list[6] = event_list
        mysql(event_list)
        return 0
    if event == 7:
        event_list.append(list_header[7])
        event_list.append("SYSTEM STATE: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[7] = [event_list[0], event_list[1], event_list[2], WORK_MODE_ST[int(event_list[3])]]
        mysql(event_list)
        return 0
    if event == 8:
        event_list.append("PROGRAM ERROR MESSAGE: ")
        event_list.append(get_val_from_buf(1, 'int'))
        msg_len = get_val_from_buf(1, "int")
        event_list.append(get_val_from_buf(msg_len, "str"))
        show_val_list[8] = event_list
        return 0
    if event == 9:
        progname_num = get_val_from_buf(1, 'int')
        for i6 in range(progname_num):
            layer = get_val_from_buf(1, 'int')
            if layer == 0:
                event_list.append("ROUTINE ")
            else:
                if layer == 0:
                    event_list.append("SUBROUTINE 1 ")
                else:
                    if layer == 0:
                        event_list.append("SUBROUTINE 2 ")
            str_len = get_val_from_buf(1, 'int')
            event_list.append("NAME:")
            event_list.append(get_val_from_buf(str_len, 'str'))
            str_len = get_val_from_buf(1, 'int')
            event_list.append("PATH:")
            event_list.append(get_val_from_buf(str_len, 'str'))
        show_val_list[9] = event_list
        return 0
    if event == 10:
        event_list.append(list_header[7])
        event_list.append("SWITCH JOG: ")
        event_list.append(str(get_val_from_buf(4, 'float')))
        show_val_list[10] = event_list
        mysql(event_list)
        return 0
    if event == 11:
        event_list.append(list_header[7])
        event_list.append("SWITCH FEED: ")
        event_list.append(str(get_val_from_buf(4, 'float')))
        show_val_list[11] = event_list
        mysql(event_list)
        return 0
    if event == 12:
        event_list.append(list_header[7])
        event_list.append("SWITCH SPINDLE: ")
        event_list.append(str(get_val_from_buf(4, 'float')))
        show_val_list[12] = event_list
        mysql(event_list)
        return 0
    if event == 13:
        event_list.append(list_header[7])
        event_list.append("BLOCK NUMB CTRL PROG: ")
        event_list.append(str(get_val_from_buf(4, 'int')))
        show_val_list[13] = event_list
        mysql(event_list)
        return 0
    if event == 14:
        event_list.append(list_header[7])
        event_list.append("TOOL NUMBER: ")
        event_list.append(str(get_val_from_buf(2, 'int')))
        show_val_list[14] = event_list
        mysql(event_list)
        return 0
    if event == 15:
        event_list.append(list_header[7])
        event_list.append("CORRECTOR NUMBER: ")
        event_list.append(str(get_val_from_buf(2, 'int')))
        show_val_list[15] = event_list
        mysql(event_list)
        return 0
    if event == 16:
        event_list.append(list_header[7])
        event_list.append("UAS: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[16] = event_list
        mysql(event_list)
        return 0
    if event == 17:
        event_list.append(list_header[7])
        event_list.append("UVR: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[17] = event_list
        mysql(event_list)
        return 0
    if event == 18:
        event_list.append(list_header[7])
        event_list.append("URL: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[18] = event_list
        mysql(event_list)
        return 0
    if event == 19:
        event_list.append(list_header[7])
        event_list.append("COMU: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[19] = event_list
        mysql(event_list)
        return 0
    if event == 20:
        event_list.append(list_header[7])
        event_list.append("CEFA: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[20] = event_list
        mysql(event_list)
        return 0
    if event == 21:
        event_list.append(list_header[7])
        event_list.append("MUSP: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[21] = event_list
        mysql(event_list)
        return 0
    if event == 22:
        event_list.append(list_header[7])
        event_list.append("REAZ: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[22] = event_list
        mysql(event_list)
        return 0
    if event == 23:
        machine_idletime_num = get_val_from_buf(1, 'int')
        for i7 in range(machine_idletime_num):
            machine_idletime_action = get_val_from_buf(1, 'int')
            machine_idletime_group_len = get_val_from_buf(1, 'int')
            if machine_idletime_action == 1:
                event_list.append('MACHINE IDLE TIME SET: ')
            else:
                event_list.append('MACHINE IDLE TIME RESET: ')
            if machine_idletime_group_len > 0:
                machine_idletime_group = get_val_from_buf(machine_idletime_group_len, 'int')
                event_list.append(machine_idletime_group)
            machine_idletime_len = get_val_from_buf(1, 'int')
            if machine_idletime_len > 0:
                machine_idletime_str = get_val_from_buf(machine_idletime_len, 'str')
                event_list.append(machine_idletime_str)
        show_val_list[23] = event_list
        return 0
    if event == 24:
        amount_symbol = get_val_from_buf(1, "int")
        event_list.append(list_header[7])
        event_list.append("PLC alarm: ")
        event_list.append(get_val_from_buf(amount_symbol, "str"))
        show_val_list[24] = event_list
        mysql(event_list)
        return 0
    if event == 25:
        amount_symbol = get_val_from_buf(1, "int")
        event_list.append(list_header[7])
        event_list.append("PLC message: ")
        event_list.append(get_val_from_buf(amount_symbol, "str"))
        show_val_list[25] = event_list
        mysql(event_list)
        return 0
    if event == 26:
        command_line_len = get_val_from_buf(1, 'int')
        event_list.append(list_header[7])
        event_list.append("COMMAND FROM PROCESS: ")
        event_list.append(get_val_from_buf(command_line_len, 'str'))
        show_val_list[26] = event_list
        mysql(event_list)
        return 0
    if event == 27:
        command_line_len = get_val_from_buf(1, 'int')
        event_list.append(list_header[7])
        event_list.append("BLOCK FROM PROCESS: ")
        event_list.append(get_val_from_buf(command_line_len, 'str'))
        show_val_list[27] = event_list
        mysql(event_list)
        return 0
    if event == 28:
        command_line_len = get_val_from_buf(1, 'int')
        event_list.append(list_header[7])
        event_list.append("COMMAND LINE: ")
        event_list.append(get_val_from_buf(command_line_len, 'str'))
        show_val_list[28] = event_list
        mysql(event_list)
        return 0
    if event == 29:
        event_part_finished = get_val_from_buf(1, 'int')
        event_list.append("Part Finished: ")
        event_list.append(get_val_from_buf(event_part_finished, 'int'))
        show_val_list[29] = event_list
        return 0
    if event == 30:
        g_functions_num = get_val_from_buf(1, 'int')
        event_list.append("G functions: ")
        event_list.append(get_val_from_buf(g_functions_num, 'str'))
        show_val_list[30] = event_list
        return 0
    if event == 31:
        event_list.append(list_header[7])
        event_list.append("RISP: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[31] = event_list
        mysql(event_list)
        return 0
    if event == 32:
        event_list.append(list_header[7])
        event_list.append("CONP: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[32] = event_list
        mysql(event_list)
        return 0
    if event == 33:
        event_list.append(list_header[7])
        event_list.append("SPEPNREQ: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[33] = event_list
        mysql(event_list)
        return 0
    if event == 34:
        event_list.append(list_header[7])
        event_list.append("ASPEPN: ")
        event_list.append(str(get_val_from_buf(1, 'int')))
        show_val_list[34] = event_list
        mysql(event_list)
        return 0
    if event == 35:
        subroutine_info_len = get_val_from_buf(1, 'int')
        event_list.append("WNCMT: ")
        event_list.append(get_val_from_buf(subroutine_info_len, 'str'))
        show_val_list[35] = event_list
        return 0
    if event == 36:
        subroutine_info_len = get_val_from_buf(1, 'int')
        event_list.append("WPRT: ")
        event_list.append(get_val_from_buf(subroutine_info_len, 'str'))
        show_val_list[36] = event_list
        return 0
    if event == 37:
        subroutine_info_len = get_val_from_buf(1, 'int')
        event_list.append("WPROG: ")
        event_list.append(get_val_from_buf(subroutine_info_len, 'str'))
        show_val_list[37] = event_list
        return 0
    if event == 38:
        subroutine_info_len = get_val_from_buf(1, 'int')
        event_list.append("WIZKD: ")
        event_list.append(get_val_from_buf(subroutine_info_len, 'str'))
        show_val_list[38] = event_list
        return 0
    if event == 39:
        event_list.append("TIME SYNCH")
        show_val_list[39] = event_list
        return 0
    if event == 40:
        event_list.append("G functions: ")
        event_list.append(get_val_from_buf(4, 'float'))
        show_val_list[40] = event_list
        return 0
    if event == 41:
        event_list.append("EVENT_ARMD_SERVICE")
        show_val_list[41] = event_list
        return 1


def mon_list_send():
    global show_val_list

    timestamp = datetime.datetime.now()

    # time.sleep(0.25)
    with closing(pymysql.connect(host=host, user=user, password=password, db=db)) as conn:
        with conn.cursor() as cursor:
            query = """UPDATE cncmon.mon SET WORK_MODE = %s, SYSTEM_STATE = %s, UAS = %s, UVR = %s, URL = %s, 
            COMU = %s, CEFA = %s, MUSP = %s, REAZ = %s, PLC_message = %s, COMMAND_LINE = %s, RISP = %s, 
            CONP = %s, SPEPNREQ = %s, ASPEPN = %s, 
            Timestamp = %s WHERE cnc_name = 'cnc310'"""
            try:
                print('monitor update')
                print(show_val_list)
                cursor.execute(query, (show_val_list[4][3],
                                       show_val_list[7][3],
                                       show_val_list[16][3],
                                       show_val_list[17][3],
                                       show_val_list[18][3],
                                       show_val_list[19][3],
                                       show_val_list[20][3],
                                       show_val_list[21][3],
                                       show_val_list[22][3],
                                       show_val_list[25][3],
                                       show_val_list[28][3],
                                       show_val_list[31][3],
                                       show_val_list[32][3],
                                       show_val_list[33][3],
                                       show_val_list[34][3],
                                       timestamp))
            except pymysql.Error as err:
                print(err)
            conn.commit()


def mysql(event_list: list) -> list:
    """
     Формеруем лист для записи в mySQL
    """
    global count_millis
    count_millis += 1

    event_list[0] = str(date) + " " + str(event_list[0]) + str(count_millis).zfill(3)  # таймштамп
    if event_list[3] != '\x00':
        if event_list[3] != "":
            mysql_list.append(event_list)

    return mysql_list


def write_to_mysql():
    """
    Записываем в базу данных  mySQL
    """
    global count_millis
    with closing(pymysql.connect(host=host,
                                 user=user,
                                 password=password,
                                 db=db)) as conn:

        with conn.cursor() as cursor:
            query = 'INSERT INTO cncmon.events VALUES (%s,%s,%s,%s)'
            try:
                cursor.executemany(query, mysql(["", "", "", ""]))
            except pymysql.Error as err:
                print(err)
            conn.commit()
            mysql_list.clear()
            count_millis = 0


def counter_event():
    """
    Считаем количество сообщений для отправки пакета в  mySQL
    """
    global counter
    counter += 1
    if counter > 100:
        write_to_mysql()
        counter = 0


def print_event(event_list: list):
    """
     Вывод в консоль
    """
    # print(*event_list)


def get_event_data() -> int:
    """
    Основная функция \n
    Читаем данные  из  buf_list в который перед эти прочитали весь бинарный фаил \n
    """
    global index
    global type_event
    crc_data_start = copy.deepcopy(index)  # Запоминаем index для чтения контрольной суммы
    s_time = get_val_from_buf(4, "time")  # прочитываем текущее время из файла
    m_time = copy.deepcopy(s_time)
    time_event = s_time[0:9] + m_time[11:15]  # формируем время сообщения
    get_val_from_buf(2, "int")  # Читаем длину сообщений
    num_proc: int = get_val_from_buf(1, "int")  # читаем количество процессов
    for i8 in range(num_proc):
        proc = get_val_from_buf(1, "int")  # номер процесса
        num_event = get_val_from_buf(2, "int")  # Количество сообщений
        for item in range(num_event):
            mon_inf_pos = get_val_from_buf(2, "int")  #
            type_event = proc_info[proc][mon_inf_pos][0]  # тип сообщения
            len_val = get_event(type_event, time_event)  # получаем длину сообщения
            index += len_val
            print_event(show_val_list[type_event])  # Не обязательно!  пичатаем в консоль сообщение
            # print(show_val_list)
            counter_event()

    crc_data_end = index  # \
    check_out = 0  # \
    for i9 in range(crc_data_start, crc_data_end):  # Вычесляем контрольную суммму
        check_ = int.from_bytes(buf_list[i], "little")  # /
        check_out ^= check_  # /

    crc_ = get_val_from_buf(1, "int")  #

    if check_out != crc_:
        # exit(8)                         # Выходим из программы с кодом ошибки - "8"
        return -1
    else:
        return 0


def start():
    """
    Старт программы 
    """
    global name_file_mon, date
    read_config()
    name_file_mon = open_file_current()  # читаем имя файла из current.inf
    read_file(name_file_mon)  # Заполняем основной лист
    load_header()  # Заполняем структуру сообщений
    date = datetime.date(list_header[10], list_header[11], list_header[12])
    get_event_data()  # Читаем основной лист состояние машины (заголовок)
    while index < list_header[2]:  # Читаем основной лист все сообщения до конца файла
        get_event_data()


def main():
    """
    Основной цикл 
    """
    global index, name_file_mon, timer_sql, timer_sql_mon

    time_changes_file = os.path.getmtime(catalog + name_file_mon)  # запоминаем время изменение файла
    time.sleep(0.03)
    while True:  # Основной цикл
        time.sleep(0.02)

        if (time.monotonic() - timer_sql) > 5:  # проверяем таймер для  записи в mySQL
            write_to_mysql()
            timer_sql = time.monotonic()

        next_time_changes_file = os.path.getmtime(catalog + name_file_mon)  # Читаем время изменения файла

        if time_changes_file != next_time_changes_file:  # Если фаил изменился то:

            buf_list.clear()  # обнуляем основной лист с бинарными данными
            read_file(name_file_mon)  # Заполняем основной лист из файла
            index_temp = index
            index = 0
            load_header()  # Заполняем структуру сообщений
            index = index_temp
            # buf_list_size = len(buf_list)
            while index < list_header[2]:
                get_event_data()  # и прочитываем новое сообщение
                if type_event == 1:  # если последнее сообщение было "NO EVENT"
                    index = index - 13  # возвращаемся на 13 байт
                    break

            if (time.monotonic() - timer_sql_mon) > 2:  # Запись в таблицу мониторинга по таймеру 1 сек.
                mon_list_send()
                timer_sql_mon = time.monotonic()

            time_changes_file = next_time_changes_file
        else:
            new_name_file_mon = open_file_current()  # читаем имя бинарного файла из current()
            if new_name_file_mon != name_file_mon:  # исли имя изменилось
                name_file_mon = new_name_file_mon
                buf_list.clear()  # обнуляем основной лист с бинарными данными
                read_file(name_file_mon)  # заполняем основной лист новыми данными
                index = 0
                start()  # начинаем все с начала


if __name__ == "__main__":  # если фаил запустили как исполняемый
    start()  # Старт программы
    main()  # Основной цикл
