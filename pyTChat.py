#!/usr/bin/python
# -*- coding: utf-8 -*-

#########################################################################
#                Copyright © 2014, GHOSTnew                             #
#########################################################################
# This program is free software: you can redistribute it and/or modify  #
# it under the terms of the GNU General Public License as published by  #
# the Free Software Foundation, either version 3 of the License, or     #
# (at your option) any later version.                                   #
#                                                                       #
# This program is distributed in the hope that it will be useful,       #
# but WITHOUT ANY WARRANTY; without even the implied warranty of        #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         #
# GNU General Public License for more details.                          #
#                                                                       #
# You should have received a copy of the GNU General Public License     #
# along with this program.  If not, see <http://www.gnu.org/licenses/>. #
#########################################################################

################# TODO ##################
# - better management of disconnections #
# - whatever you suggest                #
#########################################

import socket
import os
try:
    import ConfigParser
except:
    import configparser as ConfigParser
try:
    import thread
except:
    import _thread as thread


class User:

    def __init__(self, session):
        self.connexion = session[0]
        self.address = session[1]
        self.nick = None

    def set_nick(self, nick):
        self.nick = nick

    def get_nick(self):
        return self.nick

    def send(self, msg):
        if self.nick is not None:
            self.send_raw("\r\n\033[1A\r" + str(msg) + "\r\n" + "(you): ")
        else:
            self.send_raw(str(msg) + "\r\n")

    def send_raw(self, msg):
        self.connexion.send(str(msg).encode('utf-8'))

    def get_session(self):
        return self.connexion


class ChatServer:

    def __init__(self, port, password):
        self.port = port
        self.password = password
        self.clients = list()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):
        self.server.bind(('', port))
        self.server.listen(5)
        print("[+] Server was running on port: " + str(port))
        while True:
            #  on accepte les clients dans un thread
            session = self.server.accept()
            UnloggedUser = User(session)
            thread.start_new_thread(self.__client_handle, (UnloggedUser,))

    def __linebyline(self, client):
        buff = ""
        while True:
            data = client.get_session().recv(4096)
            try:
                data = data.decode(encoding='utf-8')
            except:
                data = " "

            if not data:
                if not buff:
                    break
            elif buff:
                data = buff + data
                buff = ""

            if '\r\n' in data:
                for line in data.splitlines(True):
                    if line.endswith('\r\n'):
                        yield line.replace("\r", "").replace("\n", "")
                    else:
                        buff = line
            else:
                buff += data

    def __client_handle(self, client):
        generator = self.__linebyline(client)
        if self.password:
            client.send_raw("Password:")
            possible_password = next(generator)
            if possible_password != self.password:
                client.send("\033[31mWrong password\033[0m\r\n")
                client.get_session().close()
                return None

        client.send(self.__get_motd())

        while client.get_nick() is None:
            client.send_raw("Your Nick:")
            possible_nick = next(generator)
            if len(possible_nick) > 10:
                possible_nick = possible_nick[:10]
            allready_exist = False
            for u in self.clients:
                if u.get_nick() is not None:
                    if u.get_nick().lower() == possible_nick.lower():
                        allready_exist = True
                        client.send("\033[31mThis nick is allready used\033[0m")
                        break

            if not allready_exist:
                if possible_nick.lower() != "server" and possible_nick != "":
                    client.set_nick(possible_nick)
                else:
                    client.send("\033[31mThis nick is reserved for server\033[0m")

        client.send_raw(
            "Commands available:\r\n"
            + "/who                  - List all users\r\n"
            + "/private <nick> <msg> - Send private message to <nick>\r\n"
            + "/exit                 - Quit the room\r\n"
            + "/clear                - Clear the screen\r\n\r\n")
        self.clients.append(client)
        client.send(self.__prepare_nick("SERVER") + ": Users = " + " ".join(str(c.get_nick()) for c in self.clients))
        self.__broadcast(self.__prepare_nick("SERVER") + ": \033[32m" + client.get_nick() + " have joined the room\033[0m")

        while True:
            try:
                block = next(generator)
            except:
                self.__client_disconnect(client)
                break

            client.send_raw("\r\033[1A\033[K\r")
            if block.startswith("/"):
                cmd = block.split(" ")
                command = cmd[0].lower()
                if command == "/exit" or command == "/quit" or command == "/q":
                    self.__client_disconnect(client)
                    break
                elif command == "/who" or command == "/list":
                    userList = " ".join(str(c.get_nick()) for c in self.clients)
                    client.send(self.__prepare_nick("SERVER") + ": Users = " + userList)
                elif command == "/private" or command == "/p":
                    if len(cmd) > 2:
                        for u in self.clients:
                            if u.get_nick().lower() == cmd[1].lower():
                                u.send("(**" + client.get_nick() + "->" + u.get_nick() + "): " + block[block.index(cmd[1]):])
                                client.send("(**" + client.get_nick() + "->" + u.get_nick() + "): " + block[block.index(cmd[1]):])
                                break
                elif command == "/clear" or command == "/cls":
                    client.send("\033[2J")
                else:
                    client.send(self.__prepare_nick("SERVER") + ": \033[31mUnknow commands\033[0m")
            else:
                if block != "":
                    self.__broadcast(self.__prepare_nick(client.get_nick()) + ": " + block)

    def __get_motd(self):
        try:
            with open("motd.txt", "r") as motd:
                return motd.read()
        except:
            return "\033[31mmotd file not found\033[0m"

    def __broadcast(self, msg):
        for client in self.clients:
            try:
                client.send(msg)
            except:
                self.__client_disconnect(client)

    def __client_disconnect(self, client):
        client.get_session().close()
        for c in self.clients:
            if c.get_nick().lower() == client.get_nick().lower():
                self.clients.remove(c)
        self.__broadcast(self.__prepare_nick("SERVER") + ": \033[33m" + client.get_nick() + " have left the room\033[0m")

    def __prepare_nick(self, nick):
        if len(nick) != 10:
            return "\033[35m" + "".join(" " for i in range(0, 10-len(nick))) + nick + "\033[0m"
        else:
            return "\033[35m" +  nick + "\033[0m"

if __name__ == '__main__':
    config = ConfigParser.ConfigParser()
    if os.path.exists("pytchat.ini"):
        #  la config existe
        config.read("pytchat.ini")
        port = config.getint("global", "port")
        password = config.get("global", "password")
        server = ChatServer(port, password)
        server.start()
    else:
        print("[-] Erreur aucun fichier de configuration trouvé.")
        print("[*] Un fichier de configuration à été généré. Merci de l'éditer.")
        config.add_section("global")
        config.set("global", "port", "1337")
        config.set("global", "password", "")
        config.write(open("pytchat.ini", "w"))
