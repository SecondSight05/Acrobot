from configparser import ConfigParser
from cryptography.fernet import Fernet
import socket, logging, sqlite3, random

class IRCClient():
    def start():
        # Get details from config file & setup stuff
        ConfigFile = ConfigParser()
        ConfigFile.read('data/config.ini')
        IRCLocation = ConfigFile['bezerk']['IRCServerLocation']
        IRCPort = int(ConfigFile['bezerk']['IRCServerPort'])
        IRCSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        EncKey = ConfigFile['bezerk']['FernetKey'].encode()
        encryption = Fernet(EncKey)
        
        # Setup logging
        IRCLog = logging.getLogger('Acrobot')
        IRCLog.setLevel(logging.DEBUG)
        LogFormatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
        ConsoleLogging = logging.StreamHandler()
        ConsoleLogging.setLevel(logging.DEBUG)
        ConsoleLogging.setFormatter(LogFormatter)
        IRCLog.addHandler(ConsoleLogging)
        
        # Connect to the IRC server
        IRCLog.info('Connecting to the IRC server at ' + IRCLocation + ':' + str(IRCPort) + '...')
        IRCSock.connect((IRCLocation, IRCPort))
        IRCSock.send('USER BRAcrobot BRAcrobot BRAcrobot :Behold... The Magical Acrobot!\n'.encode())
        IRCSock.send('NICK Acrobot\n'.encode())
        IRCSock.send('PRIVMSG nickserv :BRAuth\r\n'.encode())
        chjoin = 0
        while True:
            msg = IRCSock.recv(2048)
            #IRCLog.info('New message: ' + str(msg))
            # Let's play Ping-Pong!
            if msg.find('PING'.encode()) != -1:
                IRCSock.send("PONG :don't worry, i'm still here\r\n".encode())
                # If this is the first time seeing "PING", join the channels.
                # (This is here because my IRC server has PING in one of its first messages, despite it not being an actual PING.)
                if chjoin == 0:
                    IRCLog.info('Joining channels...')
                    IRCSock.send('JOIN #Acro_List\n'.encode())
                    #IRCSock.send('JOIN #Acro_AcroCentral\n'.encode())
                    database = sqlite3.connect('data/bezerk.db')
                    dbcursor = database.cursor()
                    dbcursor.execute('SELECT ChannelName FROM rooms')
                    for room2join in dbcursor:
                        IRCSock.send('JOIN #{}\n'.format(room2join[0]).encode())
                    dbcursor.close()
                    database.close()
                    chjoin = 1
                    IRCLog.info('Connected successfully.')
            
            # When a player joins a room, send logon_now to them privately.
            elif msg.find('JOIN'.encode()) != -1:
                if msg.find('Acrobot'.encode()) == -1:
                    JoinMessage = msg.decode('UTF-8')
                    JoinMessage = JoinMessage.split(':')
                    JoinIRCName = JoinMessage[1][0:12]
                    JoinChannel = JoinMessage[2][:-2]
                    IRCSock.send('PRIVMSG {} :logon_now\r\n'.format(JoinIRCName).encode())
            
            # Logon Processing
            elif msg.find('logon'.encode()) != -1:
                LogonMessage = msg.decode('UTF-8')
                LogonMessage = LogonMessage.split('"')
                LogonIRCName = JoinIRCName
                LogonChannel = JoinChannel
                LogonResult = Acrophobia.logon(LogonMessage[1], LogonMessage[3], encryption)
                # If the logon was successful, then send logon_accepted to them privately.
                if LogonResult == 1:
                    IRCSock.send('PRIVMSG {} :logon_accepted\r\n'.format(LogonIRCName).encode())
                    # Check if the player is in the room list channel. If they aren't, send sponsor_ad to them privately.
                    if LogonChannel != '#Acro_List':
                        IRCLog.info('Username ' + LogonMessage[1] + ' logged on to the ' + LogonChannel + ' room')
                        # Choose a random ad to be played as the "sponsor" ad.
                        with open('data/adlist.txt', 'r') as ads:
                            adlist = []
                            for ad in ads:
                                ad = ad.strip()
                                adlist.append(ad)
                        adchoice = random.choice(adlist)
                        IRCSock.send('PRIVMSG {} :sponsor_ad "{}"\r\n'.format(LogonIRCName, adchoice).encode())
                    # Otherwise, send the room list to them privately.
                    else:
                        database = sqlite3.connect('data/bezerk.db')
                        dbcursor = database.cursor()
                        IRCSock.send('PRIVMSG {} :start_list bot\r\n'.format(LogonIRCName).encode())
                        dbcursor.execute('SELECT * FROM rooms')
                        for room in dbcursor:
                            # TBD: add the player/high score counters, and the mode
                            IRCSock.send('PRIVMSG {} :list_item bot 0 "{}" 0 "{}" {} 0 "{}" 0 "Acrobot" {} "" 0 0 0 {}\r\n'.format(LogonIRCName, room[0], IRCLocation, IRCPort, room[1], room[2], room[3]).encode())
                        dbcursor.close()
                        database.close()
                        IRCSock.send('PRIVMSG {} :end_list bot\r\n'.format(LogonIRCName).encode())

class Acrophobia():
    def logon(LogonUsername, LogonPassword, encryption):
        # Get the account details from the database.
        # We're doing the checks again. (In case of a sneaky player...)
        # If any of the checks fail, return 0.
        database = sqlite3.connect('data/bezerk.db')
        dbcursor = database.cursor()
        dbcursor.execute('SELECT Username, Password, BadName, BanStatus FROM accounts WHERE Username = ?', (LogonUsername,))
        dbresults = dbcursor.fetchone()
        if dbresults is None:
            dbcursor.close()
            database.close()
            return 0
        # If the account exists in the database, then continue.
        else:
            dbcursor.close()
            database.close()
            # Check if the request password and DB password match.
            LogonPWMatch = encryption.decrypt(dbresults[1].encode()).decode()
            if LogonPassword != LogonPWMatch:
                return 0
            # If they do, then continue.
            else:
                LogonPassword = ''
                LogonPWMatch = ''
                # Check if the account has a bad name waiting to be changed.
                if dbresults[2] == 1:
                    return 0
                # If it doesn't, then continue.
                else:
                    # Check if the account is banned.
                    if dbresults[3] == 1:
                        return 0
                    # If it isn't, then the account is good to finish logon. Return 1.
                    else:
                        return 1