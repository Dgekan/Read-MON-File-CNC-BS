import os
import datetime
import struct
import copy
import functools, operator
import sqlite3
import time
import configobj



buf_list=[] # В этот лист считываем весь фаил 
list_header = [] # Заголовок файла  
proc_info = [] # Основная структура сюда записываем индекс сообщений
show_val_list=[] # Лист в котором хранится текущее состояние станка 
for i in range(41):
    show_val_list.append(i)

sql_list=[]

index: int = 0
name_file_mon = ""
database = ""
catalog = ""
type_event=0
date=""

WORK_MODE_ST = {1: "MDI", 2: "AUTO", 3: "STEP", 4: "MANU", 5: "MANJ", 6: "PROF", 7: "HOME", 8: "RESET", 0: "0"}

def read_config():
    """
    Читаем фаил конфиг 
    """
    global catalog
    global database 
    iniFile = "config.ini"
    config = configobj.ConfigObj(iniFile)
    if config.file_error ==  False:
        catalog = config["catalog"]
        database  = config["database"]
    else:
        print("Не удалось открыть файл config.ini")

        exit(2)

read_config() 

if not os.path.exists(database):
    conn = sqlite3.connect(database)   
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE Сообщения (Время text, Тип text, Значение text) """)


    

def open_file_current() -> str:
    """
    Читаем фаил current.inf
    """
    global catalog
    if os.path.exists(catalog + "current.inf"):
        file = open(catalog + "current.inf", "r")
        name_file_mon = file.read(18)
       # print("Читаем фаил", name_file_mon)
        file.close()
        return name_file_mon
    else:
        print("Не удалось открыть файл",catalog + "current.inf")

        exit(2)


def openfile(file_name: str):
    """
    file_name= 20020104093446.mon
    Читаем фаил .mon указанный в current.inf 
    в лист buf_list
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
        print("Не удалось открыть файл ", catalog + file_name, " указанный в current.inf ")
        exit(2)



def get_val_from_buf(length: int, kind: str, on_index: bool = True):
    """
    -> int, -> str, ->float, ->time \n
    length -- Количество байт (длина) \n
    kind ---  Тип к которому мы приводим \n
    on_index ---  разрешаем увиличивать индес 
    
    """
    global index
    a = b''
    index_min = index
    index_max = index + length
    if on_index:
        index += length

    if kind == "int":
        for i in range(index_min, index_max):
            a += buf_list[i]
        return int.from_bytes(a, byteorder='little', signed=False)

    elif kind == "str":
        list1 = []
        for i in range(index_min, index_max):
            if buf_list[i] != b'\x00': 
                list1.append(buf_list[i].decode('cp866'))
        return ''.join(str(x) for x in list1)

    elif kind == "time":
        for i in range(index_min, index_max):
            a += buf_list[i]
        time_ = int.from_bytes(a, byteorder='little', signed=False)
        hours = time_ // (3600 * 1000 * 10)
        minutes = (time_ - hours * 3600 * 1000 * 10) // (60 * 1000 * 10)
        seconds = (time_ - hours * 3600 * 1000 * 10 - minutes * 60 * 1000 * 10) // (1000 * 10)
        milliseconds = (time_ - hours * 3600 * 1000 * 10 - minutes * 60 * 1000 * 10 - seconds * 1000 * 10) // 10
        return str(datetime.time(hours, minutes, seconds, milliseconds))

    elif kind == "float":
        a = b''
        for i in range(index_min, index_max):
            a += buf_list[i]
        return float("{0:.4f}".format(functools.reduce(operator.add,(struct.unpack('f', a)))))


def load_header()->tuple:
    """
    Читаем заголовок файла и  записываем его в две структуры  
    """
    global date

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
   
    date=str(list_header[12])+"."+str(list_header[11])+"."+str(list_header[10])
    print(list_header)
    for proc in range(num_proc):
        kol_event = get_val_from_buf(2, "int")

        structure_kol_event = []

        for event in range(kol_event):
            structure_event = [get_val_from_buf(2, "int"), get_val_from_buf(4, "int"), get_val_from_buf(4, "int"),
                               get_val_from_buf(1, "int")]
            structure_kol_event.append(structure_event)

        proc_info.append(structure_kol_event)

def show_val(event:int,time_event:int):
    """
    Заполняем  лист show_val_list вложенным листом event_list \n
    Пример - event_list = [09:12:49.0063, SPINDLE SPEED:, 1350.0]
    """
    global index
    global date
    event_list=[]
    event_list.append(str(time_event))

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
        for i in range(system_start_data_character_files_num):
            len_ = get_val_from_buf(1, 'int')
            event_list.append(get_val_from_buf(len_, 'str'))
            len_ = get_val_from_buf(1, 'int')
            event_list.append(get_val_from_buf(len_, 'str'))
            len_ = get_val_from_buf(1, 'int')
            event_list.append(get_val_from_buf(len_, 'str'))
        show_val_list[2] = event_list
        return 0
    if event == 3:
        event_list.append("NEW DATE: ")
        event_list.append(get_val_from_buf(2, 'int'))
        event_list.append(get_val_from_buf(2, 'int'))
        event_list.append(get_val_from_buf(2, 'int'))
        show_val_list[3] = event_list
        date=str(show_val_list[3][4])+"."+str(show_val_list[3][3])+"."+str(show_val_list[3][2])
        return 0
    if event == 4:
        event_list.append("WORK MODE: ")
        event_list.append(WORK_MODE_ST[get_val_from_buf(1, 'int')])
        show_val_list[4] = event_list
        mes_sql(event_list)
        return 0
    if event == 5:
        event_list.append("FEED: ")
        event_list.append(get_val_from_buf(4, 'float'))
        show_val_list[5] = event_list
        mes_sql(event_list)
        return 0
    if event == 6:
        event_list.append("SPINDLE SPEED: ")
        event_list.append(get_val_from_buf(4, 'float'))
        show_val_list[6] = event_list
        mes_sql(event_list)
        return 0
    if event == 7:
        event_list.append("SYSTEM STATE: ")
        event_list.append(WORK_MODE_ST[get_val_from_buf(1, 'int')])
        show_val_list[7] = event_list
        mes_sql(event_list)
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
        for i in range(progname_num):
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
        event_list.append("SWITCH JOG: ")
        event_list.append(get_val_from_buf(4, 'float'))
        show_val_list[10] = event_list
        mes_sql(event_list)
        return 0
    if event == 11:
        event_list.append("SWITCH FEED: ")
        event_list.append(get_val_from_buf(4, 'float'))
        show_val_list[11] = event_list
        mes_sql(event_list)
        return 0
    if event == 12:
        event_list.append("SWITCH SPINDLE: ")
        event_list.append(get_val_from_buf(4, 'float'))
        show_val_list[12] = event_list
        mes_sql(event_list)
        return 0
    if event == 13:
        event_list.append("BLOCK NUMB CTRL PROG: ")
        event_list.append(get_val_from_buf(4, 'int'))
        show_val_list[13] = event_list
        mes_sql(event_list)
        return 0
    if event == 14:
        event_list.append("TOOL NUMBER: ")
        event_list.append(get_val_from_buf(2, 'int'))
        show_val_list[14] = event_list
        mes_sql(event_list)
        return 0
    if event == 15:
        event_list.append("CORRECTOR NUMBER: ")
        event_list.append(get_val_from_buf(2, 'int'))
        show_val_list[15] = event_list
        mes_sql(event_list)
        return 0
    if event == 16:
        event_list.append("UAS: ")
        event_list.append(get_val_from_buf(1, 'int'))
        show_val_list[16] = event_list
        mes_sql(event_list)
        return 0
    if event == 17:
        event_list.append("UVR: ")
        event_list.append(get_val_from_buf(1, 'int'))
        show_val_list[17] = event_list
        mes_sql(event_list)
        return 0
    if event == 18:
        event_list.append("URL: ")
        event_list.append(get_val_from_buf(1, 'int'))
        show_val_list[18] = event_list
        mes_sql(event_list)
        return 0
    if event == 19:
        event_list.append("COMU: ")
        event_list.append(get_val_from_buf(1, 'int'))
        show_val_list[19] = event_list
        mes_sql(event_list)
        return 0
    if event == 20:
        event_list.append("CEFA: ")
        event_list.append(get_val_from_buf(1, 'int'))
        show_val_list[20] = event_list
        mes_sql(event_list)
        return 0
    if event == 21:
        event_list.append("MUSP: ")
        event_list.append(get_val_from_buf(1, 'int'))
        show_val_list[21] = event_list
        mes_sql(event_list)
        return 0
    if event == 22:
        event_list.append("REAZ: ")
        event_list.append(get_val_from_buf(1, 'int'))
        show_val_list[22] = event_list
        mes_sql(event_list)
        return 0
    if event == 23:
        machine_idletime_num = get_val_from_buf(1, 'int')
        for i in range(machine_idletime_num):
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
        event_list.append("PLC alarm: ")
        event_list.append(get_val_from_buf(amount_symbol, "str"))
        show_val_list[24] = event_list
        mes_sql(event_list)
        return 0
    if event == 25:
        amount_symbol = get_val_from_buf(1, "int")
        event_list.append("PLC message: ")
        event_list.append(get_val_from_buf(amount_symbol, "str"))
        show_val_list[25] = event_list
        mes_sql(event_list)
        return 0
    if event == 26:
        command_line_len = get_val_from_buf(1, 'int')
        event_list.append("COMMAND FROM PROCESS: ")
        event_list.append(get_val_from_buf(command_line_len, 'str'))
        show_val_list[26] = event_list
        mes_sql(event_list)
        return 0
    if event == 27:
        command_line_len = get_val_from_buf(1, 'int')
        event_list.append("BLOCK FROM PROCESS: ")
        event_list.append(get_val_from_buf(command_line_len, 'str'))
        show_val_list[27] = event_list
        mes_sql(event_list)
        return 0
    if event == 28:
        command_line_len = get_val_from_buf(1, 'int')
        event_list.append("COMMAND LINE: ")
        event_list.append(get_val_from_buf(command_line_len, 'str'))
        show_val_list[28] = event_list
        mes_sql(event_list)
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
        event_list.append("RISP: ")
        event_list.append(get_val_from_buf(1, 'int'))
        show_val_list[31] = event_list
        mes_sql(event_list)
        return 0
    if event == 32:
        event_list.append("CONP: ")
        event_list.append(get_val_from_buf(1, 'int'))
        show_val_list[32] = event_list
        mes_sql(event_list)
        return 0
    if event == 33:
        event_list.append("SPEPNREQ: ")
        event_list.append(get_val_from_buf(1, 'int'))
        show_val_list[33] = event_list
        mes_sql(event_list)
        return 0
    if event == 34:
        event_list.append("ASPEPN: ")
        event_list.append(get_val_from_buf(1, 'int'))
        show_val_list[34] = event_list
        mes_sql(event_list)
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
        show_val_list[40]=event_list
        return 0
    if event == 41:
        event_list.append("EVENT_ARMD_SERVICE")
        show_val_list[41]=event_list
        return 1

def mes_sql(event_list:list)->tuple:
    """
    Записываем в базу данных 
    """
    global database
    global date
    event_list[0]= date + " " + event_list[0]
    sql_list.append(event_list)
    
    if len(sql_list) == 200:
        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        cursor.executemany("INSERT INTO Сообщения VALUES (?,?,?)",tuple(sql_list))
        conn.commit()
        sql_list.clear()

def mysql(event_list:list)->tuple:
    """
    
    ['2020-11-23 09:12:28.0792', 'PLC message: ', '\x00']
    """
    global count_millis
    count_millis+=1
  
    event_list[0]= str(date) +" "+ str(event_list[0]) + str(count_millis).zfill(3)
    if (event_list[2] != '\x00'):
        if (event_list[2] != ""):
            mysql_list.append(event_list)
            if  len(mysql_list)==100:
                with closing(pymysql.connect(host = host,
                                     user = user,
                                     password = password,
                                     db = db)) as conn:
                                
                    with conn.cursor() as cursor:
                        query = 'INSERT INTO cncmon.msg VALUES (%s,%s,%s)'
                        try:
                            cursor.executemany(query, mysql_list)
                        except pymysql.Error as error:
                            print(error)
                        conn.commit()
                        mysql_list.clear()
                        count_millis = 0
   
def print_event(event_list:list):

    """
     Печатаем в консоль 
    """
    print(event_list)


def get_event_data()->int:
    '''
    проходим по файлу 
    '''
    global index
    global type_event
    crc_data_start = copy.deepcopy(index)
    s_time = get_val_from_buf(4, "time")
    m_time = copy.deepcopy(s_time)
    time_event=s_time[0:9] + m_time[11:15]
    events_len = get_val_from_buf(2, "int")
    num_proc = get_val_from_buf(1, "int")
    for i in range(num_proc):
        proc = get_val_from_buf(1, "int")
        num_event = get_val_from_buf(2, "int")
        for item in range(num_event):
            mon_inf_pos = get_val_from_buf(2, "int")
            type_event = proc_info[proc][mon_inf_pos][0]
            len_val = show_val(type_event, time_event)
            index += len_val
            print_event(show_val_list[type_event])
            
    crc_data_end = index
    check_out = 0
    for i in range(crc_data_start, crc_data_end):
        check_ = int.from_bytes(buf_list[i], "little")
        check_out ^= check_

    crc_ = get_val_from_buf(1, "int")
    
    if check_out != crc_:
        return -1
    else:
        return 0

name_file_mon=open_file_current() # читаем имя файла из current.inf
openfile(name_file_mon) # Заполняем основной лист 
load_header()
get_event_data()

while index < list_header[2]:
    get_event_data()

time_changes_file = os.path.getmtime(catalog + name_file_mon)        

while True:
    time.sleep(1)
    next_time_changes_file = os.path.getmtime(catalog + name_file_mon)
    if  time_changes_file < next_time_changes_file :
        buf_list=[]
        openfile(name_file_mon)
        if type_event==1:
            index=index-13
            
        get_event_data()
        time_changes_file = next_time_changes_file
    else:
        new_name_file_mon=open_file_current() 
        if new_name_file_mon != name_file_mon:
            name_file_mon = new_name_file_mon 
            openfile(name_file_mon) 
            time.sleep(1)
            index=0
            load_header()
            get_event_data()
            
            while index < list_header[2]:
                get_event_data()
            

