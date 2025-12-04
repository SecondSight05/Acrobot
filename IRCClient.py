from configparser import ConfigParser
from cryptography.fernet import Fernet
import socket, logging, sqlite3, random, threading, string, time

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
        ConfigFile = ''
        #CONVERSION TO DB - REMOVE WHEN DONE
        RoomState = ConfigParser()
        RoomState.read('data/roomstate.ini')
        RoomState['playerloc'] = {}
        RoomState['playername'] = {}
        RoomState['playerfmf'] = {}
        RoomState['playerinroom'] = {}
        RoomStateSync = ConfigParser()
        RoomStateSync.read('data/roomstate_sync.ini')
        RoomStateSync['playeronline'] = {}
        RoomStateSync['comptime'] = {}
        RoomStateSync['companswer'] = {}
        RoomStateSync['compnum'] = {}
        RoomStateSync['votedfor'] = {}
        
        # Setup the Find My Friends RoomState key for each player
        #CONVERSION TO DB - REMOVE WHEN DONE
        database = sqlite3.connect('data/bezerk.db')
        dbcursor = database.cursor()
        dbcursor.execute('SELECT * FROM accounts')
        for player in dbcursor:
            RoomStateSync['playeronline'][player[0]] = '0'
        with open('data/roomstate_sync.ini', 'w') as rssync:
            RoomStateSync.write(rssync)
        
        # Setup the RoomState keys for each room
        #CONVERSION TO DB - REMOVE WHEN DONE
        dbcursor.execute('SELECT * FROM rooms')
        for room in dbcursor:
            RoomState[room[1]] = {}
            RoomState[room[1]]['roomplayercount'] = '0'
            RoomState[room[1]]['roomhighscore'] = '0'
            RoomState[room[1]]['roommode'] = ''
            RoomState[room[1]]['roomplayerinfo'] = ''
            RoomStateSync[room[1]] = {}
            RoomStateSync[room[1]]['roomgametype'] = '0'
            RoomStateSync[room[1]]['companswercount'] = '0'
            RoomStateSync[room[1]]['companswers'] = ''
            RoomStateSync[room[1]]['category'] = ''
            RoomStateSync[room[1]]['roomcurrentstate'] = 'start_game'
            RoomStateSync[room[1]]['voterlist'] = ''
            RoomStateSync[room[1]]['speedwinner'] = ''
        dbcursor.close()
        database.close()
        
        # Setup the rooms in the RoomState DB
        RoomStateDB = sqlite3.connect('data/roomstate.db')
        RSDBCursor = RoomStateDB.cursor()
        database = sqlite3.connect('data/bezerk.db')
        dbcursor = database.cursor()
        dbcursor.execute('SELECT ChannelName FROM rooms')
        for room in dbcursor:
            RSDBCursor.execute('CREATE TABLE ' + room[0] + ' (playercount TEXT, highscore TEXT, mode TEXT, playerinfo TEXT, gametype TEXT, currentstate TEXT, companswercount TEXT, companswers TEXT, category TEXT, voterlist TEXT, speedwinner TEXT)')
            RSDBCursor.execute('INSERT INTO ' + room[0] + ' VALUES (0, 0, ?, ?, 0, "start_game", 0, ?, ?, ?, ?)', ('', '', '', '', '', ''))
        RoomStateDB.commit()
        dbcursor.close()
        database.close()
        RSDBCursor.close()
        RoomStateDB.close()
        
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
            # Uncomment the line below to see IRC messages when they come in.
            #IRCLog.info('New message: ' + str(msg))
            # Let's play Ping-Pong!
            if msg.find('PING'.encode()) != -1:
                IRCSock.send("PONG :don't worry, i'm still here\r\n".encode())
                # If this is the first time seeing "PING", join the channels.
                # (This is here because my IRC server has PING in one of its first messages, despite it not being an actual PING.)
                if chjoin == 0:
                    IRCLog.info('Joining channels...')
                    chjoinmsg = ''
                    IRCSock.send('JOIN #Acro_List\n'.encode())
                    database = sqlite3.connect('data/bezerk.db')
                    dbcursor = database.cursor()
                    dbcursor.execute('SELECT ChannelName FROM rooms')
                    for room2join in dbcursor:
                        chjoinmsg = chjoinmsg + 'JOIN #{}\n'.format(room2join[0])
                    IRCSock.send('{}'.format(chjoinmsg).encode())
                    dbcursor.close()
                    database.close()
                    chjoin = 1
                    IRCLog.info('Connected successfully.')
            
            # When a player joins a room, send logon_now to them privately.
            elif msg.find('JOIN'.encode()) != -1:
                if msg.find('Acrobot'.encode()) == -1:
                    JoinMessage = msg.decode('UTF-8')
                    JoinMessage = JoinMessage.split(':')
                    JoinIRCName = JoinMessage[1].split('!')
                    JoinIRCName = JoinIRCName[0]
                    JoinChannel = JoinMessage[2][:-2]
                    RoomState['playerloc'][JoinIRCName] = JoinChannel
                    RoomStateDB = sqlite3.connect('data/roomstate.db')
                    RSDBCursor = RoomStateDB.cursor()
                    RSDBCursor.execute('SELECT ircname FROM player WHERE ircname = ?', (JoinIRCName,))
                    dbresults = RSDBCursor.fetchone()
                    if dbresults is None:
                        RSDBCursor.execute('INSERT INTO player VALUES (?, ?, ?, 0, 0)', ('', JoinIRCName, JoinChannel))
                        #TEMP OH GOD - REPLACE PLEASE REPLACE WITH A BETTER THING
                        RSDBCursor.execute('INSERT INTO round VALUES (?, ?, ?, ?, ?, 0)', (JoinIRCName, '', '', '', ''))
                    else:
                        RSDBCursor.execute('UPDATE player SET location = ? WHERE ircname = ?', (JoinChannel, JoinIRCName))
                    RoomStateDB.commit()
                    RSDBCursor.close()
                    RoomStateDB.close()
                    IRCSock.send('PRIVMSG {} :logon_now\r\n'.format(JoinIRCName).encode())
            
            # Logon Processing
            elif msg.find('logon'.encode()) != -1:
                LogonMessage = msg.decode('UTF-8')
                LogonMessage = LogonMessage.split('"')
                LogonIRCName = LogonMessage[0].split('!')
                LogonIRCName = LogonIRCName[0].split(':')
                LogonIRCName = LogonIRCName[1]
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('SELECT location FROM player WHERE ircname = ?', (LogonIRCName,))
                dbresults = RSDBCursor.fetchone()
                LogonChannel = dbresults[0]
                LogonResult = Acrophobia.logon(LogonMessage[1], LogonMessage[3], encryption)
                # If the logon was successful, then send logon_accepted to them privately.
                if LogonResult == 1:
                    IRCSock.send('PRIVMSG {} :logon_accepted\r\n'.format(LogonIRCName).encode())
                    RSDBCursor.execute('UPDATE player SET location = ? WHERE ircname = ?', (LogonChannel[1:], LogonIRCName))
                    RSDBCursor.execute('UPDATE player SET username = ? WHERE ircname = ?', (LogonMessage[1], JoinIRCName))
                    RoomStateDB.commit()
                    #RoomState['playerloc'][LogonIRCName] = LogonChannel[1:]
                    #RoomState['playername'][LogonIRCName] = LogonMessage[1]
                    #RoomState['playerfmf'][LogonMessage[1]] = LogonIRCName
                    #RoomState['playerinroom'][LogonIRCName] = '0'
                    #RoomStateSync['playeronline'][LogonMessage[1]] = '1'
                    with open('data/roomstate_sync.ini', 'w') as rssync:
                        RoomStateSync.write(rssync)
                    # Check if the player is in the room list channel. If they aren't, send sponsor_ad to them privately.
                    if LogonChannel != '#Acro_List':
                        IRCLog.info('Username ' + LogonMessage[1] + ' logged on to the ' + LogonChannel + ' room')
                        RSDBCursor.close()
                        RoomStateDB.close()
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
                        RoomJoinMsg = ''
                        for room in dbcursor:
                            # TBD: properly add the high score counter
                            #RoomPlayerCount = int(RoomState[room[1]]['roomplayercount'])
                            #RoomHighScore = int(RoomState[room[1]]['roomhighscore'])
                            #RoomMode = RoomState[room[1]]['roommode']
                            RSDBCursor.execute('SELECT playercount, highscore, mode FROM ' + room[1])
                            dbresults = RSDBCursor.fetchone()
                            RoomPlayerCount = dbresults[0]
                            RoomHighScore = dbresults[1]
                            RoomMode = dbresults[2]
                            RoomJoinMsg = RoomJoinMsg + f'PRIVMSG {LogonIRCName} :list_item bot 0 "{room[0]}" 0 "{IRCLocation}" {IRCPort} 0 "{room[1]}" 0 "Acrobot" {room[2]} "{RoomMode}" {str(RoomPlayerCount)} {str(RoomHighScore)} 0 {room[3]}\r\n'
                        IRCSock.send('{}'.format(RoomJoinMsg).encode())
                        dbcursor.close()
                        database.close()
                        RSDBCursor.close()
                        RoomStateDB.close()
                        IRCSock.send('PRIVMSG {} :end_list bot\r\n'.format(LogonIRCName).encode())
            
            # Set the player up for starting the actual game.
            elif msg.find('start_play'.encode()) != -1:
                StartPlayIRCName = msg[1:25].decode('UTF-8')
                StartPlayIRCName = StartPlayIRCName.split('!')
                StartPlayIRCName = StartPlayIRCName[0]
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                # Get the room's name and current state.
                #StartPlayChannel = RoomState['playerloc'][StartPlayIRCName]
                RSDBCursor.execute('SELECT location FROM player WHERE ircname = ?', (StartPlayIRCName,))
                dbresults = RSDBCursor.fetchone()
                StartPlayChannel = dbresults[0]
                #StartPlayRoomState = RoomStateSync[StartPlayChannel]['roomcurrentstate']
                RSDBCursor.execute('SELECT currentstate FROM ' + StartPlayChannel)
                dbresults = RSDBCursor.fetchone()
                StartPlayRoomState = dbresults[0]
                IRCSock.send('PRIVMSG {} :current_state {}\r\n'.format(StartPlayIRCName, StartPlayRoomState).encode())
                # Get the room name/data from the DB and the player's username from RoomState.
                database = sqlite3.connect('data/bezerk.db')
                dbcursor = database.cursor()
                dbcursor.execute('SELECT RoomName FROM rooms WHERE ChannelName = ?', (StartPlayChannel,))
                dbresults = dbcursor.fetchone()
                StartPlayRoomName = dbresults[0]
                dbcursor.execute('SELECT * FROM rooms WHERE RoomName = ?', (StartPlayRoomName,))
                dbresults = dbcursor.fetchone()
                dbcursor.close()
                database.close()
                #StartPlayUsername = RoomState['playername'][StartPlayIRCName]
                RSDBCursor.execute('SELECT username FROM player WHERE ircname = ?', (StartPlayIRCName,))
                dbresults = RSDBCursor.fetchone()
                StartPlayUsername = dbresults[0]
                # Send the welcome message to the player privately.
                IRCSock.send('PRIVMSG {} :chat "Welcome to {}"\r\n'.format(StartPlayIRCName, StartPlayRoomName).encode())
                # Send the player join message to the room publicly.
                IRCSock.send('PRIVMSG #{} :player add "{}" 0 "{}"\r\n'.format(StartPlayChannel, StartPlayIRCName, StartPlayUsername).encode())
                # Check if there isn't anyone else in the room.
                #RoomPlayerCount = int(RoomState[StartPlayChannel]['roomplayercount'])
                RSDBCursor.execute('SELECT playercount FROM ' + StartPlayChannel)
                dbresults = RSDBCursor.fetchone()
                RoomPlayerCount = int(dbresults[0])
                if RoomPlayerCount > 0:
                    # If false, send the info for the other players to the new player privately.
                    listplayeradd = 1
                    #listplayerinfo = RoomState[StartPlayChannel]['roomplayerinfo'].split('/')
                    RSDBCursor.execute('SELECT playerinfo FROM ' + StartPlayChannel)
                    dbresults = RSDBCursor.fetchone()
                    listplayerinfo = dbresults[0].split(',')
                    while listplayeradd <= RoomPlayerCount:
                        #listplayeritem = listplayerinfo[listplayeradd].split(',')
                        #ListPlayerIRCName = listplayeritem[0]
                        #ListPlayerScore = listplayeritem[1]
                        #ListPlayerUsername = listplayeritem[2]
                        ListPlayerIRCName = listplayerinfo[listplayeradd]
                        RSDBCursor.execute('SELECT username, roomscore FROM player WHERE ircname = ?', (ListPlayerIRCName,))
                        dbresults = RSDBCursor.fetchone()
                        ListPlayerScore = str(dbresults[1])
                        ListPlayerUsername = dbresults[0]
                        IRCSock.send('PRIVMSG {} :player add "{}" {} "{}"\r\n'.format(StartPlayIRCName, ListPlayerIRCName, ListPlayerScore, ListPlayerUsername).encode())
                        listplayeradd += 1
                # Update the room info to show a new player.
                #RoomState[StartPlayChannel]['roomplayercount'] = str(int(RoomState[StartPlayChannel]['roomplayercount']) + 1)
                RSDBCursor.execute('SELECT playercount FROM ' + StartPlayChannel)
                dbresults = RSDBCursor.fetchone()
                RSDBCursor.execute('UPDATE ' + StartPlayChannel + ' SET playercount = ?', (str(int(dbresults[0]) + 1,)))
                modeselector = str(int(dbresults[0]) + 1)
                #RoomHighScore = int(RoomState[StartPlayChannel]['roomhighscore'])
                #RoomMode = RoomState[StartPlayChannel]['roommode']
                #RoomState[StartPlayChannel]['roomplayerinfo'] = RoomState[StartPlayChannel]['roomplayerinfo'] + '/' +  StartPlayIRCName + ',0,' + StartPlayUsername
                RSDBCursor.execute('SELECT playerinfo FROM ' + StartPlayChannel)
                dbresults = RSDBCursor.fetchone()
                RSDBCursor.execute('UPDATE ' + StartPlayChannel + ' SET playerinfo = ?', (dbresults[0] + ',' + StartPlayIRCName,))
                #RoomState['playerinroom'][StartPlayIRCName] = '1'
                RSDBCursor.execute('UPDATE player SET ingameroom = "1" WHERE ircname = ?', (StartPlayIRCName,))
                # Set the game type (Play or Practice) if that game type isn't already running, and a certain amount of players are in the room.
                #if RoomStateSync[StartPlayChannel]['roomgametype'] == '0':
                RSDBCursor.execute('SELECT gametype FROM ' + StartPlayChannel)
                dbresults = RSDBCursor.fetchone()
                if dbresults[0] == '0':
                    # Practice Mode
                    #if RoomState[StartPlayChannel]['roomplayercount'] == '1' or RoomState[StartPlayChannel]['roomplayercount'] == '2':
                    if modeselector == '1' or modeselector == '2':
                        #RoomState[StartPlayChannel]['roommode'] = 'Practice'
                        #RoomStateSync[StartPlayChannel]['roomgametype'] = '2'
                        RSDBCursor.execute('UPDATE ' + StartPlayChannel + ' SET mode = "Practice"')
                        RSDBCursor.execute('UPDATE ' + StartPlayChannel + ' SET gametype = "2"')
                        IRCSock.send('PRIVMSG {} :chat "There must be at least 3 players to start a game - You will be in Practice mode until then."\r\n'.format(StartPlayIRCName).encode())
                        threading.Thread(target=GameLoop.practice, args=(IRCSock, RoomStateSync, StartPlayChannel)).start()
                #elif RoomStateSync[StartPlayChannel]['roomgametype'] == '2':
                elif dbresults[0] == '2':
                    # Play Mode
                    #if int(RoomState[StartPlayChannel]['roomplayercount']) >= 3:
                    if int(modeselector) >= 3:
                        #RoomState[StartPlayChannel]['roommode'] = 'Play'
                        #RoomStateSync[StartPlayChannel]['roomgametype'] = '1'
                        RSDBCursor.execute('UPDATE ' + StartPlayChannel + ' SET mode = "Play"')
                        RSDBCursor.execute('UPDATE ' + StartPlayChannel + ' SET gametype = "1"')
                        IRCSock.send('PRIVMSG #{} :chat "A third player has joined - Get ready to play!"\r\n'.format(StartPlayChannel).encode())
                        threading.Thread(target=GameLoop.play, args=(IRCSock, RoomStateSync, StartPlayChannel)).start()
                RoomStateDB.commit()
                RSDBCursor.close()
                RoomStateDB.close()
            
            # Logoff - Remove player from room.
            elif msg.find('logoff ip'.encode()) != -1 or msg.find('QUIT'.encode()) != -1:
                LogoffIRCName = msg[1:25].decode('UTF-8')
                LogoffIRCName = LogoffIRCName.split('!')
                LogoffIRCName = LogoffIRCName[0]
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('SELECT location, ingameroom FROM player WHERE ircname = ?', (LogoffIRCName,))
                dbresults = RSDBCursor.fetchone()
                #if RoomState['playerloc'][LogoffIRCName].find('Acro_List') == -1 and RoomState['playerinroom'][LogoffIRCName] == '1':
                if dbresults[0].find('Acro_List') == -1 and dbresults[1] == '1':
                    # Get the channel that the player is in.
                    #LogoffChannel = RoomState['playerloc'][LogoffIRCName]
                    LogoffChannel = dbresults[0]
                    # Find the other two pieces of info from RoomState.
                    #logoffinfo = RoomState[LogoffChannel]['roomplayerinfo'].split('/')
                    RSDBCursor.execute('SELECT playerinfo FROM ' + LogoffChannel)
                    dbresults = RSDBCursor.fetchone()
                    logoffinfo = dbresults[0].split(',')
                    for loitem in logoffinfo:
                        if loitem != '':
                            if loitem.find(LogoffIRCName) != -1:
                                #loitem = loitem.split(',')
                                #LogoffScore = loitem[1]
                                #LogoffUsername = loitem[2]
                                RSDBCursor.execute('SELECT username, roomscore FROM player WHERE ircname = ?', (LogoffIRCName,))
                                dbresults = RSDBCursor.fetchone()
                                # do i even need these now?
                                LogoffScore = str(dbresults[1])
                                LogoffUsername = dbresults[0]
                                IRCLog.info('Username ' + LogoffUsername + ' logged off of the #' + LogoffChannel + ' room')
                    # Get the index for the player's info in RoomState.
                    #LogoffIndex = logoffinfo.index(LogoffIRCName + ',' + LogoffScore + ',' + LogoffUsername)
                    LogoffIndex = logoffinfo.index(LogoffIRCName)
                    # Remove the player from the room in RoomState.
                    logoffinfo.pop(LogoffIndex)
                    logoffinfo = ','.join(logoffinfo)
                    #RoomState[LogoffChannel]['roomplayercount'] = str(int(RoomState[LogoffChannel]['roomplayercount']) - 1)
                    RSDBCursor.execute('SELECT playercount FROM ' + LogoffChannel)
                    dbresults = RSDBCursor.fetchone()
                    RSDBCursor.execute('UPDATE ' + LogoffChannel + ' SET playercount = ?', (str(int(dbresults[0]) - 1,)))
                    RSDBCursor.execute('UPDATE ' + LogoffChannel + ' SET playerinfo = ?', (logoffinfo,))
                    #RoomState['playerinroom'][LogoffIRCName] = '0'
                    #RoomStateSync['playeronline'][LogoffUsername] = '0'
                    RSDBCursor.execute('UPDATE player SET location = "" WHERE ircname = ?', (LogoffIRCName,))
                    RSDBCursor.execute('UPDATE player SET ingameroom = "0" WHERE ircname = ?', (LogoffIRCName,))
                    RSDBCursor.execute('UPDATE player SET roomscore = 0 WHERE ircname = ?', (LogoffIRCName,))
                    # Update the in-game player list.
                    IRCSock.send('PRIVMSG #{} :player remove "{}" {} "{}"\r\n'.format(LogoffChannel, LogoffIRCName, LogoffScore, LogoffUsername).encode())
                    # Check if the room's game type needs to be changed.
                    #if RoomStateSync[LogoffChannel]['roomgametype'] == '2':
                    RSDBCursor.execute('SELECT playercount, gametype FROM ' + LogoffChannel)
                    dbresults = RSDBCursor.fetchone()
                    if dbresults[1] ==  '1':
                        if int(dbresults[0]) < 3:
                            # If there's less than 3 players, change to Practice mode.
                            RSDBCursor.execute('UPDATE ' + StartPlayChannel + ' SET mode = "Practice"')
                            RSDBCursor.execute('UPDATE ' + StartPlayChannel + ' SET gametype = "2"')
                            IRCSock.send('PRIVMSG #{} :chat "There aren\'t enough players left to continue this game. Practice mode will start at the end of the round."\r\n'.format(LogoffChannel,).encode())
                    elif dbresults[1] ==  '2':
                        #if int(RoomState[LogoffChannel]['roomplayercount']) == 0:
                        if dbresults[0] == '0':
                            # If there are no players left, close the loop for that room.
                            #RoomStateSync[LogoffChannel]['roomgametype'] = '0'
                            #RoomState[LogoffChannel]['roommode'] = ''
                            RSDBCursor.execute('UPDATE ' + StartPlayChannel + ' SET mode = ""')
                            RSDBCursor.execute('UPDATE ' + StartPlayChannel + ' SET gametype = "0"')
                            with open('data/roomstate_sync.ini', 'w') as rssync:
                                RoomStateSync.write(rssync)
                    RoomStateDB.commit()
                RSDBCursor.close()
                RoomStateDB.close()
            
            # Find My Friends
            elif msg.find('command find_player'.encode()) != -1:
                FMFIRCName = msg[1:25].decode('UTF-8')
                FMFIRCName = FMFIRCName.split('!')
                FMFIRCName = FMFIRCName[0]
                FMFUsername = msg.decode('UTF-8').split('"')
                FMFUsername = FMFUsername[1]
                # Check if the requested player is in the DB.
                database = sqlite3.connect('data/bezerk.db')
                dbcursor = database.cursor()
                dbcursor.execute('SELECT Username FROM accounts WHERE Username = ?', (FMFUsername,))
                dbresults = dbcursor.fetchone()
                if dbresults is None:
                    # If they aren't, send player_not_found.
                    dbcursor.close()
                    database.close()
                    IRCSock.send('PRIVMSG {} :player_not_found "{}"\r\n'.format(FMFIRCName, FMFUsername).encode())
                else:
                    # Otherwise, check if the requested player is online.
                    #if RoomStateSync['playeronline'][FMFUsername] == '0' or dbresults is None:
                    RoomStateDB = sqlite3.connect('data/roomstate.db')
                    RSDBCursor = RoomStateDB.cursor()
                    RSDBCursor.execute('SELECT username FROM player WHERE username = ?', (FMFUsername,))
                    dbrfmf = RSDBCursor.fetchone()
                    if dbrfmf is None or dbresults is None:
                        RSDBCursor.close()
                        RoomStateDB.close()
                        dbcursor.close()
                        database.close()
                        # If they aren't, send player_not_found.
                        IRCSock.send('PRIVMSG {} :player_not_found "{}"\r\n'.format(FMFIRCName, FMFUsername).encode())
                    else:
                        # Otherwise, check if the requested player is in #Acro_List.
                        #FMFIRCReq = RoomState['playerfmf'][FMFUsername]
                        #if RoomState['playerloc'][FMFIRCReq].find('Acro_List') != -1:
                        RSDBCursor.execute('SELECT location FROM player WHERE username = ?', (FMFUsername,))
                        dbresults = RSDBCursor.fetchone()
                        if dbresults[0].find('Acro_List') != -1:
                            RSDBCursor.close()
                            RoomStateDB.close()
                            dbcursor.close()
                            database.close()
                            # If they are, set the information to show they're choosing a room.
                            # Don't bother with getting the other details properly. They won't be shown anyway.
                            fmfroomname = 'a'
                            FMFChannel = 'b'
                            fmfisclean = '1'
                            RoomMode = 'c'
                            RoomPlayerCount = '0'
                            RoomHighScore = '0'
                            FMFRoomList = '1'
                        else:
                            # Otherwise, get all the information needed to show what room the requested player is in.
                            #FMFChannel = RoomState['playerloc'][FMFIRCReq]
                            FMFChannel = dbresults[0]
                            dbcursor.execute('SELECT RoomName, IsClean FROM rooms WHERE ChannelName = ?', (FMFChannel,))
                            dbresults = dbcursor.fetchone()
                            fmfroomname = dbresults[0]
                            fmfisclean = str(dbresults[1])
                            dbcursor.close()
                            database.close()
                            #RoomPlayerCount = RoomState[FMFChannel]['roomplayercount']
                            #RoomHighScore = RoomState[FMFChannel]['roomhighscore']
                            #RoomMode = RoomState[FMFChannel]['roommode']
                            RSDBCursor.execute('SELECT playercount, highscore, mode FROM ' + FMFChannel)
                            dbresults = RSDBCursor.fetchone()
                            RoomPlayerCount = dbresults[0]
                            RoomHighScore = dbresults[1]
                            RoomMode = dbresults[2]
                            FMFRoomList = '0'
                        IRCSock.send(f'PRIVMSG {FMFIRCName} :player_found "{FMFUsername}" "{fmfroomname}" 0 "{IRCLocation}" {IRCPort} 0 "{FMFChannel}" 0 "Acrobot" {fmfisclean} "{RoomMode}" {RoomPlayerCount} {RoomHighScore} {FMFRoomList}\r\n'.encode())
            
            # When an acro is sent during the composition round.
            elif msg.find('response answer'.encode()) != -1:
                RAAcro = msg.decode('UTF-8')
                RAAcro = RAAcro.split('"')
                RATime = RAAcro[0].split(' ')
                RAAcro = RAAcro[1]
                RAPlayer = RATime[6]
                RATime = RATime[5]
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                #rsch = RoomState['playerloc'][RAPlayer]
                RSDBCursor.execute('SELECT location FROM player WHERE ircname = ?', (RAPlayer,))
                dbresults = RSDBCursor.fetchone()
                rsch = dbresults[0]
                #RoomStateSync[rsch]['companswers'] = RoomStateSync[rsch]['companswers'] + ',' + RAPlayer
                RSDBCursor.execute('SELECT companswers FROM ' + rsch)
                dbresults = RSDBCursor.fetchone()
                updanswers = dbresults[0] + ',' + RAPlayer
                RSDBCursor.execute('UPDATE ' + rsch + ' SET companswers = ?', (updanswers,))
                #RoomStateSync[rsch]['companswercount'] = str(int(RoomStateSync[rsch]['companswercount']) + 1)
                RSDBCursor.execute('SELECT companswercount FROM ' + rsch)
                dbresults = RSDBCursor.fetchone()
                cactemp = str(int(dbresults[0]) + 1)
                RSDBCursor.execute('UPDATE ' + rsch + ' SET companswercount = ?', (cactemp,))
                #RoomStateSync['comptime'][RAPlayer] = str(RATime)
                RSDBCursor.execute('UPDATE round SET comptime = ? WHERE ircname = ?', (RATime, RAPlayer))
                #RoomStateSync['companswer'][RAPlayer] = RAAcro
                RSDBCursor.execute('UPDATE round SET companswer = ? WHERE ircname = ?', (RAAcro, RAPlayer))
                #RoomStateSync['compnum'][RAPlayer] = RoomStateSync[rsch]['companswercount']
                RSDBCursor.execute('SELECT companswercount FROM ' + rsch)
                dbresults = RSDBCursor.fetchone()
                RSDBCursor.execute('UPDATE round SET compnum = ? WHERE ircname = ?', (dbresults[0], RAPlayer))
                #RoomStateSync['votedfor'][RAPlayer] = ''
                RSDBCursor.execute('UPDATE round SET votedfor = "" WHERE ircname = ?', (RAPlayer,))
                # If this is the first acro submitted, then set the player to win the speed bonus.
                # Uh... maybe change this later? Comptime was already a thing...
                #if RoomStateSync[rsch]['speedwinner'] == '':
                    #RoomStateSync[rsch]['speedwinner'] = RAPlayer
                RSDBCursor.execute('SELECT speedwinner FROM ' + rsch)
                dbresults = RSDBCursor.fetchone()
                if dbresults[0] == '':
                    RSDBCursor.execute('UPDATE ' + rsch + ' SET speedwinner = ?', (RAPlayer,))
                RoomStateDB.commit()
                IRCSock.send('PRIVMSG #{} :answer_received {}\r\n'.format(rsch, cactemp).encode())
                RSDBCursor.execute('SELECT username FROM player WHERE ircname = ?', (RAPlayer,))
                dbresults = RSDBCursor.fetchone()
                rausername = dbresults[0]
                RSDBCursor.close()
                RoomStateDB.close()
                RAAcro = RAAcro.replace("''", '"')
                IRCLog.info('Acro submitted by ' + rausername + ': ' + RAAcro)
            
            # When a vote is sent during the voting round.
            # !!! OLD AND BAD - REMOVE ONCE FULLY REPLACED !!!
            #elif msg.find('response vote'.encode()) != -1:
                # examples below
                # :ip3232249858!UnknownUse@ PRIVMSG Acrobot :response vote ip1234567890 1
                # :ip3232249858!UnknownUse@ PRIVMSG Acrobot :response vote ip1234567891 1
                # :ip3232249858!UnknownUse@ PRIVMSG Acrobot :response vote ip1234567890 1
                # NOTE: if there's two ' next to each other, that's a ". change it to that.
                # NOTE 2: VOTES CAN BE CHANGED!!!
                #RVVoted = msg.decode('UTF-8')
                #RVVoted = RVVoted.split(' ')
                #RVPlayer = RVVoted[0].split('!')
                #RVPlayer = RVPlayer[0].split(':')
                #RVPlayer = RVPlayer[1]
                #RVVoted = RVVoted[5]
                #print('RVPLAYER: ' + RVPlayer)
                #print('RVVOTED: ' + RVVoted)
                #RoomStateDB = sqlite3.connect('data/roomstate.db')
                #RSDBCursor = RoomStateDB.cursor()
                ##RoomStateSync['votedfor'][RVPlayer] = RVVoted
                #RSDBCursor.execute('UPDATE round SET votedfor = ? WHERE ircname = ?', (RVVoted, RVPlayer))
                ## If the player hasn't voted yet on this round, add them to the voterlist.
                #RSDBCursor.execute('SELECT location FROM player WHERE ircname = ?', (RVPlayer,))
                #dbresults = RSDBCursor.fetchone()
                #rsch = dbresults[0]
                ##vtrlistchk = RoomStateSync[RoomState['playerloc'][RVPlayer]]['voterlist'].split(',')
                #RSDBCursor.execute('SELECT voterlist FROM ' + rsch)
                #dbresults = RSDBCursor.fetchone()
                #vtrlistchk = dbresults[0].split(',')
                #if RVPlayer not in vtrlistchk:
                    ##RoomStateSync[RoomState['playerloc'][RVPlayer]]['voterlist'] = RoomStateSync[RoomState['playerloc'][RVPlayer]]['voterlist'] + ',' + RVPlayer
                    #rvtemp = dbresults[0] + ',' + RVPlayer
                    #RSDBCursor.execute('UPDATE ' + rsch + ' SET voterlist = ?', (rvtemp,))
                #RoomStateDB.commit()
                #RSDBCursor.close()
                #RoomStateDB.close()
            
            # When a vote is sent during the voting round.
            elif msg.find('response vote'.encode()) != -1:
                RVVoted = msg.decode('UTF-8')
                RVVoted = RVVoted.split(' ')
                RVPlayer = RVVoted[0].split('!')
                RVPlayer = RVPlayer[0].split(':')
                RVPlayer = RVPlayer[1]
                RVVoted = RVVoted[5]
                print('RVPLAYER: ' + RVPlayer)
                print('RVVOTED: ' + RVVoted)
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('UPDATE round SET votedfor = ? WHERE ircname = ?', (RVVoted, RVPlayer))
                #don't think i need voterlist on this new one
                RoomStateDB.commit()
                RSDBCursor.close()
                RoomStateDB.close()
            
            # When a category is selected by the winning player.
            elif msg.find('response category'.encode()) != -1:
                RCCategory = msg.decode('UTF-8')
                RCCategory = RCCategory.split(' ')
                RCPlayer = RCCategory[0].split('!')
                RCCategory = RCCategory[5]
                RCPlayer = RCPlayer[0].split(':')
                RCPlayer = RCPlayer[1]
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('SELECT location FROM player WHERE ircname = ?', (RCPlayer,))
                dbresults = RSDBCursor.fetchone()
                rsch = dbresults[0]
                #RoomStateSync[RoomState['playerloc'][RCPlayer]]['category'] = RCCategory
                RSDBCursor.execute('UPDATE ' + rsch + ' SET category = ?', (RCCategory,))
                RoomStateDB.commit()
                RSDBCursor.close()
                RoomStateDB.close()
            
            # Problem Player Complaints
            # TBD: QUOTES ARENT REMOVED (thankfully this doesn't effect acros)
            # TBD: figure out how to kick people out with enough complaints - it can't just be a certain amount, it could be abused
            elif msg.find('complain'.encode()) != -1:
                ComplainPlayer = msg.decode('UTF-8')
                ComplainReason = ComplainPlayer.split(':complain ')
                ComplainPlayer = ComplainPlayer.split('"')
                ComplainType = ComplainPlayer[0].split(' ')
                ComplainPlayer = ComplainPlayer[1]
                ComplainIRCName = ComplainType[0].split('!')
                ComplainType = int(ComplainType[5])
                ComplainReason = ComplainReason[1].split('{} "{}" '.format(str(ComplainType), ComplainPlayer))
                ComplainReason = ComplainReason[1].split('\r\n')
                ComplainReason = ComplainReason[0][:-1]
                ComplainIRCName = ComplainIRCName[0].split(':')
                ComplainIRCName = ComplainIRCName[1]
                ComplainTime = time.time()
                ComplainTimeDoc = time.strftime("%a, %d %b %Y %H:%M:%S", time.gmtime(ComplainTime))
                ComplainTime = time.strftime("%a-%d%b%Y-%H'%M'%S", time.gmtime(ComplainTime))
                if ComplainType == 1:
                    ComplainType = 'Bad Language'
                elif ComplainType == 2:
                    ComplainType = 'Harassment'
                else:
                    ComplainType = 'Other'
                ComplainReport = f'Player Game Name: {ComplainPlayer}\nPlayer IRC Name: {ComplainIRCName}\nReport Type: {ComplainType}\nReport Reason: {ComplainReason}\nReport Time: {ComplainTimeDoc}'
                ComplainFile = open('data/report-' + ComplainTime + '.txt', 'w')
                ComplainFile.write(ComplainReport)
                ComplainFile.close()
                IRCSock.send('PRIVMSG {} :chat "Thank you! Your complaint has been sent."\r\n'.format(ComplainIRCName).encode())
            
            # TEMPORARY face-off round auto start
            elif msg.find('chat "!fo '.encode()) != -1:
                foauto = msg.decode('UTF-8')
                foauto = foauto.split(' ')
                foa1st = foauto[5]
                foa2nd = foauto[6].split('"')
                foa2nd = foa2nd[0]
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('UPDATE player SET roomscore = ? WHERE username = ?', (30, foa1st))
                RSDBCursor.execute('UPDATE player SET roomscore = ? WHERE username = ?', (20, foa2nd))
                RoomStateDB.commit()
                RSDBCursor.close()
                RoomStateDB.close()
                IRCSock.send('PRIVMSG {} :chat "Your request has been granted. {} and {} had better be prepared..."\r\n'.format(foauto[2], foa1st, foa2nd).encode())
            
            # Logging chat messages.
            elif msg.find('chat "'.encode()) != -1:
                ChatMessage = msg.decode('UTF-8')
                ChatMessage = ChatMessage.split('chat "')
                ChatIRCName = ChatMessage[0].split('!')
                ChatMessage = ChatMessage[1][:-3]
                ChatMessage = ChatMessage.replace("''", '"')
                ChatIRCName = ChatIRCName[0].split(':')
                ChatIRCName = ChatIRCName[1]
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('SELECT username FROM player WHERE ircname = ?', (ChatIRCName,))
                dbresults = RSDBCursor.fetchone()
                ChatUsername = dbresults[0]
                RSDBCursor.close()
                RoomStateDB.close()
                IRCLog.info('Chat message from <' + ChatUsername + '>: ' + ChatMessage)

class GameLoop():
    def practice(IRCSock, RoomStateSync, GLChannel):
        AcroLetters = 3
        AcroCategory = 'General Acrophobia'
        PracticeLoop = True
        PracticeLoop = GameLoop.loopcheck(GLChannel, 0)
        #time.sleep(4)
        #while PracticeLoop is True:
            # Composition Round (Practice)
            #if PracticeLoop == True:
                #IRCSock.send('PRIVMSG #{} :start_comp_round 2500 60000 1 "{}" "{}"\r\n'.format(GLChannel, Acrophobia.generateacro(AcroLetters), AcroCategory).encode())
            #PracticeLoop = GameLoop.loopcheck(GLChannel, 0, RoomStateSync)
            #time.sleep(78)
            # If there wasn't any composition round submissions, skip the category picker round.
            #if int(RoomStateSync[GLChannel]['companswercount']) > 0 and PracticeLoop == True:
                # In Practice Mode, the first person to submit an acro chooses the category.
                #CategoryChooser = RoomStateSync[GLChannel]['companswers'].split(',')
                #CategoryChooser = CategoryChooser[1]
                # Category Picker Round (Practice)
                #if PracticeLoop == True:
                    #IRCSock.send('PRIVMSG #{} :start_categories 2500 5000 1 "{}"\r\n'.format(GLChannel, CategoryChooser).encode())
                #PracticeLoop = GameLoop.loopcheck(GLChannel, 0, RoomStateSync)
                # Get the categories and show them to the player.
                #CategoryList = Acrophobia.getcategories()
                #if PracticeLoop == True:
                    #IRCSock.send('PRIVMSG #{} :start_list category\r\n'.format(GLChannel).encode())
                    #IRCSock.send('PRIVMSG #{} :list_item category 0 "{}"\r\n'.format(GLChannel, CategoryList[0]).encode())
                    #IRCSock.send('PRIVMSG #{} :list_item category 1 "{}"\r\n'.format(GLChannel, CategoryList[1]).encode())
                    #IRCSock.send('PRIVMSG #{} :list_item category 2 "{}"\r\n'.format(GLChannel, CategoryList[2]).encode())
                    #IRCSock.send('PRIVMSG #{} :list_item category 3 "General Acrophobia"\r\n'.format(GLChannel).encode())
                    #IRCSock.send('PRIVMSG #{} :end_list category\r\n'.format(GLChannel).encode())
                #PracticeLoop = GameLoop.loopcheck(GLChannel, 0, RoomStateSync)
                #time.sleep(10)
                # If the bottom category or no category is chosen, set the next category to General Acrophobia.
                #if RoomStateSync[GLChannel]['category'] == '' or RoomStateSync[GLChannel]['category'] == '3':
                    #AcroCategory = 'General Acrophobia'
                # Otherwise, set the category to the one that was chosen.
                #else:
                    #AcroCategory = CategoryList[int(RoomStateSync[GLChannel]['category'])]
            # Increase the amount of letters in the next acronym by one. If it's over 7, set it back to 3.
            #AcroLetters += 1
            #if AcroLetters > 7:
                #AcroLetters = 3
            # Empty out the composition round answers.
            #if PracticeLoop == True:
                #RoomStateSync[GLChannel]['companswers'] = ''
                #RoomStateSync[GLChannel]['companswercount'] = '0'
                #RoomStateSync[GLChannel]['category'] = ''
            #with open('data/roomstate_sync.ini', 'w') as rssync:
                #RoomStateSync.write(rssync)
            #PracticeLoop = GameLoop.loopcheck(GLChannel, 0, RoomStateSync)
    
    def play(IRCSock, RoomStateSync, GLChannel):
        AcroLetters = 3
        AcroCategory = 'General Acrophobia'
        AcroRound = 1
        PlayLoop = True
        PlayLoop = GameLoop.loopcheck(GLChannel, 1)
        IRCSock.send('PRIVMSG #{} :start_game 8250\r\n'.format(GLChannel).encode())
        time.sleep(15)
        while PlayLoop is True:
            # Composition Round
            IRCSock.send('PRIVMSG #{} :start_comp_round 2500 60000 {} "{}" "{}"\r\n'.format(GLChannel, str(AcroRound), Acrophobia.generateacro(AcroLetters), AcroCategory).encode())
            PlayLoop = GameLoop.loopcheck(GLChannel, 1)
            time.sleep(78)
            RoomStateDB = sqlite3.connect('data/roomstate.db')
            RSDBCursor = RoomStateDB.cursor()
            #if int(RoomStateSync[GLChannel]['companswercount']) > 0 and PlayLoop == True:
            RSDBCursor.execute('SELECT companswercount FROM ' + GLChannel)
            dbresults = RSDBCursor.fetchone()
            cactemp = dbresults[0]
            if int(dbresults[0]) > 0 and PlayLoop == True:
                #AcroVotingTime = Acrophobia.givevotingtime(RoomStateSync[GLChannel]['companswercount'])
                AcroVotingTime = Acrophobia.givevotingtime(cactemp)
                #AcroAnswers = RoomStateSync[GLChannel]['companswers'].split(',')
                RSDBCursor.execute('SELECT companswers FROM ' + GLChannel)
                dbresults = RSDBCursor.fetchone()
                AcroAnswers = dbresults[0].split(',')
                IRCSock.send('PRIVMSG #{} :start_voting_round 2500 {}000 {}\r\n'.format(GLChannel, str(AcroVotingTime), AcroRound).encode())
                IRCSock.send('PRIVMSG #{} :start_list answer {} 1\r\n'.format(GLChannel, cactemp).encode())
                complistcount = 1
                while complistcount < int(cactemp) + 1:
                    RSDBCursor.execute('SELECT companswer FROM round WHERE ircname = ?', (AcroAnswers[complistcount],))
                    dbresults = RSDBCursor.fetchone()
                    IRCSock.send('PRIVMSG #{} :list_item answer {} "{}" "{}"\r\n'.format(GLChannel, str(complistcount - 1), AcroAnswers[complistcount], dbresults[0]).encode())
                    complistcount += 1
                RSDBCursor.close()
                RoomStateDB.close()
                IRCSock.send('PRIVMSG #{} :end_list answer\r\n'.format(GLChannel).encode())
                PlayLoop = GameLoop.loopcheck(GLChannel, 1)
                time.sleep(AcroVotingTime + 15)
                print('Doing Winner Calculation Now')
                #AcroRoundWinner, AcroRoundVotes = Acrophobia.calcvotewinner(RoomStateSync, GLChannel, AcroAnswers)
                AcroRoundWinner = Acrophobia.calcvotewinner(GLChannel)
                print('Vote Reveal Starting Now')
                IRCSock.send('PRIVMSG #{} :start_list vote_count\r\n'.format(GLChannel).encode())
                roundendcount = 1
                while roundendcount < int(cactemp) + 1:
                    #ADD AFTER SESSION:
                    #1. check if the player voted or not
                    #2. voters bonus points
                    # If the player didn't vote, then they lose all points gained during this round.
                    RoomStateDB = sqlite3.connect('data/roomstate.db')
                    RSDBCursor = RoomStateDB.cursor()
                    RSDBCursor.execute('SELECT votedfor FROM round WHERE ircname = ?', (AcroAnswers[roundendcount],))
                    dbresults = RSDBCursor.fetchone()
                    notlosingvotes = 1
                    #if RoomStateSync['votedfor'][AcroAnswers[roundendcount]] == '':
                    if dbresults[0] == '':
                        notlosingvotes = 0
                    # If the player voted for the winner, then they get a Voters Bonus Point.
                    votersbp = 0
                    #if RoomStateSync['votedfor'][AcroAnswers[roundendcount]] == AcroRoundWinner:
                    if dbresults[0] == AcroRoundWinner:
                        votersbp = 1
                    RSDBCursor.execute('SELECT roundscore FROM round WHERE ircname = ?', (AcroAnswers[roundendcount],))
                    dbresults = RSDBCursor.fetchone()
                    IRCSock.send('PRIVMSG #{} :list_item vote_count {} "{}" {} {} {}\r\n'.format(GLChannel, str(roundendcount - 1), AcroAnswers[roundendcount], str(dbresults[0]), notlosingvotes, votersbp).encode())
                    roundendcount += 1
                IRCSock.send('PRIVMSG #{} :end_list vote_count\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :start_list voted_for\r\n'.format(GLChannel).encode())
                roundendcount = 1
                #while roundendcount < int(RoomStateSync[GLChannel]['companswercount']) + 1:
                while roundendcount < int(cactemp) + 1:
                    #ADD AFTER SESSION:
                    #prevent traceback if a player doesn't vote
                    #MIGHT BE FIXED. the autoplay bots don't like me right now.
                    RSDBCursor.execute('SELECT votedfor FROM round WHERE ircname = ?', (AcroAnswers[roundendcount],))
                    dbresults = RSDBCursor.fetchone()
                    IRCSock.send('PRIVMSG #{} :list_item voted_for 1 "{}" "{}"\r\n'.format(GLChannel, AcroAnswers[roundendcount], dbresults[0]).encode())
                    roundendcount += 1
                IRCSock.send('PRIVMSG #{} :end_list voted_for\r\n'.format(GLChannel).encode())
                #ADD SCORE KEEPING AFTER SESSION
                RunFaceoff = 0
                IRCSock.send('PRIVMSG #{} :start_list score\r\n'.format(GLChannel).encode())
                roundendcount = 1
                AcroSpeedWinner = ''
                while roundendcount < int(cactemp) + 1:
                    # Get the player's current score and round score from the RoomState DB.
                    RSDBCursor.execute('SELECT roomscore FROM player WHERE ircname = ?', (AcroAnswers[roundendcount],))
                    dbresults = RSDBCursor.fetchone()
                    playercurrentscore = dbresults[0]
                    print(AcroAnswers[roundendcount] + ' current score: ' + str(dbresults[0]))
                    RSDBCursor.execute('SELECT roundscore FROM round WHERE ircname = ?', (AcroAnswers[roundendcount],))
                    dbresults = RSDBCursor.fetchone()
                    # Add the points gained this round to the new score total.
                    playernewscore = dbresults[0] + playercurrentscore
                    print(AcroAnswers[roundendcount] + ' points added: ' + str(dbresults[0]))
                    # If the player was the point winner, then add the Acro Bonus to their new score.
                    if AcroAnswers[roundendcount] == AcroRoundWinner:
                        playernewscore += AcroLetters
                        print(AcroAnswers[roundendcount] + ' ab now total: ' + str(playernewscore))
                    # If the player got a Voters Bonus Point (and they're not the point winner), add it to their new score.
                    RSDBCursor.execute('SELECT votedfor FROM round WHERE ircname = ?', (AcroAnswers[roundendcount],))
                    dbresults = RSDBCursor.fetchone()
                    if dbresults[0] == AcroRoundWinner and AcroAnswers[roundendcount] != AcroRoundWinner:
                        playernewscore += 1
                        print(AcroAnswers[roundendcount] + ' vbp now total: ' + str(playernewscore))
                    # However, if they didn't vote, then this is where they lose all their points gained this round. :(
                    playerlosepoints = 0
                    if dbresults[0] == '':
                        playerlosepoints = 1
                    # If the player was the fastest this round, then add two Speed Bonus Points to their new score (unless they lost their points).
                    RSDBCursor.execute('SELECT speedwinner FROM ' + GLChannel)
                    dbresults = RSDBCursor.fetchone()
                    if AcroSpeedWinner == '':
                        playernewscore += 2
                        AcroSpeedWinner = dbresults[0]
                        print(AcroAnswers[roundendcount] + ' sb now total: ' + str(playernewscore))
                    # If the point loss check earlier wasn't successful, then add the points to the RoomState DB.
                    if playerlosepoints == 0:
                        RSDBCursor.execute('UPDATE player SET roomscore = ? WHERE ircname = ?', (playernewscore, AcroAnswers[roundendcount]))
                        print(AcroAnswers[roundendcount] + ' new total: ' + str(playernewscore))
                    else:
                        playernewscore = playercurrentscore
                    # Get how long it took for the player to submit from the RoomState DB.
                    RSDBCursor.execute('SELECT comptime FROM round WHERE ircname = ?', (AcroAnswers[roundendcount],))
                    dbresults = RSDBCursor.fetchone()
                    # Send the score update IRC message.
                    IRCSock.send('PRIVMSG #{} :list_item score {} "{}" {} {}\r\n'.format(GLChannel, str(roundendcount - 1), AcroAnswers[roundendcount], str(playernewscore), str(dbresults[0])).encode())
                    roundendcount += 1
                    # If the player's new score is 30 or more points, set the face-off round to be started.
                    if playernewscore >= 30:
                        RunFaceoff = 1
                #if RoomStateSync[GLChannel]['speedwinner'] != '':
                    #AcroSpeedWinner = RoomStateSync[GLChannel]['speedwinner']
                RoomStateDB.commit()
                RSDBCursor.close()
                RoomStateDB.close()
                IRCSock.send('PRIVMSG #{} :start_scores 1 "{}" {} "{}" 2\r\n'.format(GLChannel, AcroRoundWinner, str(AcroLetters), AcroSpeedWinner).encode())
                IRCSock.send('PRIVMSG #{} :end_list score\r\n'.format(GLChannel).encode())
                PlayLoop = GameLoop.loopcheck(GLChannel, 1)
                time.sleep(45)
                # If the face-off round is not starting next, go to the category picker.
                if RunFaceoff == 0:
                    IRCSock.send('PRIVMSG #{} :start_categories 2500 5000 1 "{}"\r\n'.format(GLChannel, AcroRoundWinner).encode())
                    CategoryList = Acrophobia.getcategories()
                    IRCSock.send('PRIVMSG #{} :start_list category\r\n'.format(GLChannel).encode())
                    IRCSock.send('PRIVMSG #{} :list_item category 0 "{}"\r\n'.format(GLChannel, CategoryList[0]).encode())
                    IRCSock.send('PRIVMSG #{} :list_item category 1 "{}"\r\n'.format(GLChannel, CategoryList[1]).encode())
                    IRCSock.send('PRIVMSG #{} :list_item category 2 "{}"\r\n'.format(GLChannel, CategoryList[2]).encode())
                    IRCSock.send('PRIVMSG #{} :list_item category 3 "General Acrophobia"\r\n'.format(GLChannel).encode())
                    IRCSock.send('PRIVMSG #{} :end_list category\r\n'.format(GLChannel).encode())
                    time.sleep(10)
                    RoomStateDB = sqlite3.connect('data/roomstate.db')
                    RSDBCursor = RoomStateDB.cursor()
                    RSDBCursor.execute('SELECT category FROM ' + GLChannel)
                    dbresults = RSDBCursor.fetchone()
                    RSDBCursor.close()
                    RoomStateDB.close()
                    # If the bottom category or no category is chosen, set the next category to General Acrophobia.
                    #if RoomStateSync[GLChannel]['category'] == '' or RoomStateSync[GLChannel]['category'] == '3':
                    if dbresults[0] == '' or dbresults[0] == '3':
                        AcroCategory = 'General Acrophobia'
                    # Otherwise, set the category to the one that was chosen.
                    else:
                        #AcroCategory = CategoryList[int(RoomStateSync[GLChannel]['category'])]
                        AcroCategory = CategoryList[int(dbresults[0])]
            AcroLetters += 1
            if AcroLetters > 7:
                AcroLetters = 3
            RoomStateDB = sqlite3.connect('data/roomstate.db')
            RSDBCursor = RoomStateDB.cursor()
            #RoomStateSync[GLChannel]['companswers'] = ''
            RSDBCursor.execute('UPDATE ' + GLChannel + ' SET companswers = ""')
            #RoomStateSync[GLChannel]['companswercount'] = '0'
            RSDBCursor.execute('UPDATE ' + GLChannel + ' SET companswercount = "0"')
            #RoomStateSync[GLChannel]['category'] = ''
            RSDBCursor.execute('UPDATE ' + GLChannel + ' SET category = ""')
            #RoomStateSync[GLChannel]['speedwinner'] = ''
            RSDBCursor.execute('UPDATE ' + GLChannel + ' SET speedwinner = ""')
            #with open('data/roomstate_sync.ini', 'w') as rssync:
                #RoomStateSync.write(rssync)
            RoomStateDB.commit()
            RSDBCursor.close()
            RoomStateDB.close()
            # Every 3 rounds (or before the face-off), have an interstitial break.
            RunAdBreak = 0
            if AcroRound % 3 == 0:
                RunAdBreak = 1
            if RunFaceoff == 1:
                RunAdBreak = 1
            AcroRound += 1
            if RunAdBreak == 1:
                InterstitialList = Acrophobia.getinterstitials()
                #IRCSock.send('PRIVMSG #{} :start_list download_ad\r\n'.format(GLChannel).encode())
                #IRCSock.send('PRIVMSG #{} :list_item download_ad 1 {}\r\n'.format(GLChannel, InterstitialList[0]).encode())
                #time.sleep(0.2)
                #IRCSock.send('PRIVMSG #{} :list_item download_ad 2 {}\r\n'.format(GLChannel, InterstitialList[1]).encode())
                #time.sleep(0.2)
                #IRCSock.send('PRIVMSG #{} :list_item download_ad 3 {}\r\n'.format(GLChannel, InterstitialList[2]).encode())
                #time.sleep(0.2)
                #IRCSock.send('PRIVMSG #{} :end_list download_ad\r\n'.format(GLChannel).encode())
                #IRCSock.send('PRIVMSG #{} :start_ad 2500 20000 1\r\n'.format(GLChannel).encode())
                #IRCSock.send('PRIVMSG #{} :start_list play_ad\r\n'.format(GLChannel).encode())
                #IRCSock.send('PRIVMSG #{} :list_item play_ad 1 {}\r\n'.format(GLChannel, InterstitialList[0]).encode())
                #IRCSock.send('PRIVMSG #{} :list_item play_ad 2 {}\r\n'.format(GLChannel, InterstitialList[1]).encode())
                #IRCSock.send('PRIVMSG #{} :list_item play_ad 3 {}\r\n'.format(GLChannel, InterstitialList[2]).encode())
                #IRCSock.send('PRIVMSG #{} :end_list play_ad\r\n'.format(GLChannel).encode())
                PlayLoop = GameLoop.loopcheck(GLChannel, 1)
                #time.sleep(45)
            PlayLoop = GameLoop.loopcheck(GLChannel, 1)
            # Once someone reaches 30 or more points, start the face-off round.
            if RunFaceoff == 1:
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('SELECT ircname, location, roomscore FROM player WHERE location = ? ORDER BY roomscore DESC LIMIT 3', (GLChannel,))
                dbresults = RSDBCursor.fetchall()
                FOFirstPlace = dbresults[0][0]
                FOSecondPlace = dbresults[1][0]
                FOSecondTie = '0'
                if dbresults[1][2] == dbresults[2][2]:
                    FOSecondTie = '1'
                    RSDBCursor.execute('SELECT ircname, comptime FROM round WHERE ircname = ? OR ircname = ? ORDER BY comptime DESC LIMIT 2', (dbresults[1][0], dbresults[2][0]))
                    fotmp = RSDBCursor.fetchall()
                    if fotmp[1][1] < fotmp[0][1]:
                        FOSecondPlace == dbresults[2][0]
                RSDBCursor.execute('SELECT playerinfo FROM ' + GLChannel)
                dbresults = RSDBCursor.fetchone()
                FOPlayerList = dbresults[0].split(',')
                RSDBCursor.close()
                RoomStateDB.close()
                FOPlayerList.pop(0)
                print('FOFirstPlace: ' + FOFirstPlace)
                print('FOSecondPlace: ' + FOSecondPlace)
                # Player Rules / Faceoff Intro
                # (Left: Players, Right: Voters)
                for foplayer in FOPlayerList:
                    if foplayer == FOFirstPlace or foplayer == FOSecondPlace:
                        IRCSock.send('PRIVMSG {} :start_rules faceoff_player 16250\r\n'.format(foplayer).encode())
                    else:
                        IRCSock.send('PRIVMSG {} :start_faceoff 2500 21250 {} "{}" "{}"\r\n'.format(foplayer, FOSecondTie, FOFirstPlace, FOSecondPlace).encode())
                time.sleep(20)
                # Player Round 1 / Voter Rules
                FOR1Acro = Acrophobia.generateacro(3)
                for foplayer in FOPlayerList:
                    if foplayer == FOFirstPlace or foplayer == FOSecondPlace:
                        IRCSock.send('PRIVMSG {} :start_faceoff_comp_round 2500 20000 1 "{}"\r\n'.format(foplayer, FOR1Acro).encode())
                    else:
                        IRCSock.send('PRIVMSG {} :start_rules faceoff_voter 16250\r\n'.format(foplayer).encode())
                time.sleep(38)
                # Player Round 2 / Voter Round 1
                FOR2Acro = Acrophobia.generateacro(4)
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('SELECT companswer FROM round WHERE ircname = ? OR ircname = ?', (FOFirstPlace, FOSecondPlace))
                dbresults = RSDBCursor.fetchall()
                foR1p1answer = dbresults[0][0]
                foR1p2answer = dbresults[1][0]
                if foR1p1answer == '':
                    foR1p1answer = 'No answer over here!'
                if foR1p2answer == '':
                    foR1p2answer = 'No answer was given...'
                RSDBCursor.execute('UPDATE ' + GLChannel + ' SET companswers = ""')
                RSDBCursor.execute('UPDATE ' + GLChannel + ' SET companswercount = "0"')
                RoomStateDB.commit()
                RSDBCursor.close()
                RoomStateDB.close()
                for foplayer in FOPlayerList:
                    if foplayer == FOFirstPlace or foplayer == FOSecondPlace:
                        IRCSock.send('PRIVMSG {} :start_faceoff_comp_round 2500 20000 2 "{}"\r\n'.format(foplayer, FOR2Acro).encode())
                    else:
                        IRCSock.send('PRIVMSG {} :start_faceoff_voting_round 2500 14000 1 "{}"\r\n'.format(foplayer, FOR1Acro).encode())
                IRCSock.send('PRIVMSG #{} :start_list answer\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item answer 0 "{}" "{}"\r\n'.format(GLChannel, FOFirstPlace, foR1p1answer).encode())
                IRCSock.send('PRIVMSG #{} :list_item answer 1 "{}" "{}"\r\n'.format(GLChannel, FOSecondPlace, foR1p2answer).encode())
                IRCSock.send('PRIVMSG #{} :end_list answer\r\n'.format(GLChannel).encode())
                time.sleep(26)
                AcroRoundWinner = Acrophobia.calcvotewinner(GLChannel)
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('SELECT roundscore FROM round WHERE ircname = ? OR ircname = ?', (FOFirstPlace, FOSecondPlace))
                dbresults = RSDBCursor.fetchall()
                FOFirstScore = dbresults[0][0]
                FOSecondScore = dbresults[1][0]
                RSDBCursor.close()
                RoomStateDB.close()
                IRCSock.send('PRIVMSG #{} :start_face_scores 1\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :start_list vote_count\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item vote_count 0 "{}" {}\r\n'.format(GLChannel, FOFirstPlace, dbresults[0][0]).encode())
                IRCSock.send('PRIVMSG #{} :list_item vote_count 1 "{}" {}\r\n'.format(GLChannel, FOSecondPlace, dbresults[1][0]).encode())
                IRCSock.send('PRIVMSG #{} :end_list vote_count\r\n'.format(GLChannel).encode())
                time.sleep(1)
                IRCSock.send('PRIVMSG #{} :start_list faceoff_score\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item faceoff_score 0 "{}" {}\r\n'.format(GLChannel, FOFirstPlace, str(FOFirstScore)).encode())
                IRCSock.send('PRIVMSG #{} :list_item faceoff_score 1 "{}" {}\r\n'.format(GLChannel, FOSecondPlace, str(FOSecondScore)).encode())
                IRCSock.send('PRIVMSG #{} :end_list faceoff_score\r\n'.format(GLChannel).encode())
                time.sleep(20)
                # Player Round 3 / Voter Round 2
                FOR3Acro = Acrophobia.generateacro(5)
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('SELECT companswer FROM round WHERE ircname = ? OR ircname = ?', (FOFirstPlace, FOSecondPlace))
                dbresults = RSDBCursor.fetchall()
                foR2p1answer = dbresults[0][0]
                foR2p2answer = dbresults[1][0]
                if foR2p1answer == '':
                    foR2p1answer = 'No answer over here!'
                if foR2p2answer == '':
                    foR2p2answer = 'No answer was given...'
                RSDBCursor.execute('UPDATE ' + GLChannel + ' SET companswers = ""')
                RSDBCursor.execute('UPDATE ' + GLChannel + ' SET companswercount = "0"')
                RoomStateDB.commit()
                RSDBCursor.close()
                RoomStateDB.close()
                for foplayer in FOPlayerList:
                    if foplayer == FOFirstPlace or foplayer == FOSecondPlace:
                        IRCSock.send('PRIVMSG {} :start_faceoff_comp_round 2500 20000 3 "{}"\r\n'.format(foplayer, FOR3Acro).encode())
                    else:
                        IRCSock.send('PRIVMSG {} :start_faceoff_voting_round 2500 14000 2 "{}"\r\n'.format(foplayer, FOR2Acro).encode())
                IRCSock.send('PRIVMSG #{} :start_list answer\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item answer 0 "{}" "{}"\r\n'.format(GLChannel, FOFirstPlace, foR2p1answer).encode())
                IRCSock.send('PRIVMSG #{} :list_item answer 1 "{}" "{}"\r\n'.format(GLChannel, FOSecondPlace, foR2p2answer).encode())
                IRCSock.send('PRIVMSG #{} :end_list answer\r\n'.format(GLChannel).encode())
                time.sleep(26)
                AcroRoundWinner = Acrophobia.calcvotewinner(GLChannel)
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('SELECT roundscore FROM round WHERE ircname = ? OR ircname = ?', (FOFirstPlace, FOSecondPlace))
                dbresults = RSDBCursor.fetchall()
                FOFirstScore = FOFirstScore + dbresults[0][0]
                FOSecondScore = FOSecondScore + dbresults[1][0]
                RSDBCursor.close()
                RoomStateDB.close()
                IRCSock.send('PRIVMSG #{} :start_face_scores 2\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :start_list vote_count\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item vote_count 0 "{}" {}\r\n'.format(GLChannel, FOFirstPlace, dbresults[0][0]).encode())
                IRCSock.send('PRIVMSG #{} :list_item vote_count 1 "{}" {}\r\n'.format(GLChannel, FOSecondPlace, dbresults[1][0]).encode())
                IRCSock.send('PRIVMSG #{} :end_list vote_count\r\n'.format(GLChannel).encode())
                time.sleep(1)
                IRCSock.send('PRIVMSG #{} :start_list faceoff_score\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item faceoff_score 0 "{}" {}\r\n'.format(GLChannel, FOFirstPlace, str(FOFirstScore)).encode())
                IRCSock.send('PRIVMSG #{} :list_item faceoff_score 1 "{}" {}\r\n'.format(GLChannel, FOSecondPlace, str(FOSecondScore)).encode())
                IRCSock.send('PRIVMSG #{} :end_list faceoff_score\r\n'.format(GLChannel).encode())
                time.sleep(20)
                # Player End Message / Voter Round 3
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('SELECT companswer FROM round WHERE ircname = ? OR ircname = ?', (FOFirstPlace, FOSecondPlace))
                dbresults = RSDBCursor.fetchall()
                foR3p1answer = dbresults[0][0]
                foR3p2answer = dbresults[1][0]
                if foR3p1answer == '':
                    foR3p1answer = 'No answer over here!'
                if foR3p2answer == '':
                    foR3p2answer = 'No answer was given...'
                RSDBCursor.execute('UPDATE ' + GLChannel + ' SET companswers = ""')
                RSDBCursor.execute('UPDATE ' + GLChannel + ' SET companswercount = "0"')
                RoomStateDB.commit()
                RSDBCursor.close()
                RoomStateDB.close()
                for foplayer in FOPlayerList:
                    if foplayer == FOFirstPlace or foplayer == FOSecondPlace:
                        IRCSock.send('PRIVMSG {} :chat "And that\'s it! The results will be revealed in just a moment."\r\n'.format(foplayer).encode())
                    else:
                        IRCSock.send('PRIVMSG {} :start_faceoff_voting_round 2500 14000 3 "{}"\r\n'.format(foplayer, FOR3Acro).encode())
                IRCSock.send('PRIVMSG #{} :start_list answer\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item answer 0 "{}" "{}"\r\n'.format(GLChannel, FOFirstPlace, foR3p1answer).encode())
                IRCSock.send('PRIVMSG #{} :list_item answer 1 "{}" "{}"\r\n'.format(GLChannel, FOSecondPlace, foR3p2answer).encode())
                IRCSock.send('PRIVMSG #{} :end_list answer\r\n'.format(GLChannel).encode())
                time.sleep(26)
                AcroRoundWinner = Acrophobia.calcvotewinner(GLChannel)
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                RSDBCursor.execute('SELECT roundscore FROM round WHERE ircname = ? OR ircname = ?', (FOFirstPlace, FOSecondPlace))
                dbresults = RSDBCursor.fetchall()
                FOFirstScore = FOFirstScore + dbresults[0][0]
                FOSecondScore = FOSecondScore + dbresults[1][0]
                RSDBCursor.close()
                RoomStateDB.close()
                IRCSock.send('PRIVMSG #{} :start_face_scores 3\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :start_list vote_count\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item vote_count 0 "{}" {}\r\n'.format(GLChannel, FOFirstPlace, dbresults[0][0]).encode())
                IRCSock.send('PRIVMSG #{} :list_item vote_count 1 "{}" {}\r\n'.format(GLChannel, FOSecondPlace, dbresults[1][0]).encode())
                IRCSock.send('PRIVMSG #{} :end_list vote_count\r\n'.format(GLChannel).encode())
                time.sleep(1)
                IRCSock.send('PRIVMSG #{} :start_list faceoff_score\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item faceoff_score 0 "{}" {}\r\n'.format(GLChannel, FOFirstPlace, str(FOFirstScore)).encode())
                IRCSock.send('PRIVMSG #{} :list_item faceoff_score 1 "{}" {}\r\n'.format(GLChannel, FOSecondPlace, str(FOSecondScore)).encode())
                IRCSock.send('PRIVMSG #{} :end_list faceoff_score\r\n'.format(GLChannel).encode())
                time.sleep(20)
                # Final Results
                IRCSock.send('PRIVMSG #{} :start_final_scores 21250\r\n'.format(GLChannel).encode())
                time.sleep(28)
                RoomStateDB = sqlite3.connect('data/roomstate.db')
                RSDBCursor = RoomStateDB.cursor()
                IRCSock.send('PRIVMSG #{} :start_list score\r\n'.format(GLChannel).encode())
                foscorereset = 0
                for foplayer in FOPlayerList:
                    RSDBCursor.execute('UPDATE round SET roundscore = 0 WHERE ircname = ?', (foplayer,))
                    RSDBCursor.execute('UPDATE round SET votedfor = "" WHERE ircname = ?', (foplayer,))
                    RSDBCursor.execute('UPDATE player SET roomscore = 0 WHERE ircname = ?', (foplayer,))
                    IRCSock.send('PRIVMSG #{} :list_item score {} "{}" 0 0\r\n'.format(GLChannel, str(foscorereset), foplayer).encode())
                    foscorereset += 1
                IRCSock.send('PRIVMSG #{} :end_list score\r\n'.format(GLChannel).encode())
                RoomStateDB.commit()
                RSDBCursor.close()
                RoomStateDB.close()
                AcroLetters = 3
                AcroCategory = 'General Acrophobia'
                AcroRound = 1
                IRCSock.send('PRIVMSG #{} :start_game 8250\r\n'.format(GLChannel).encode())
                PlayLoop = GameLoop.loopcheck(GLChannel, 1)
                time.sleep(15)
    
    def loopcheck(channel, isplaymode):
        RoomStateDB = sqlite3.connect('data/roomstate.db')
        RSDBCursor = RoomStateDB.cursor()
        RSDBCursor.execute('SELECT gametype FROM ' + channel)
        dbresults = RSDBCursor.fetchone()
        RSDBCursor.close()
        RoomStateDB.close()
        if isplaymode == 0:
            #if RoomStateSync[channel]['roomgametype'] == '0' or RoomStateSync[channel]['roomgametype'] == '1':
            if dbresults[0] == '0' or dbresults[0] == '1':
                return False
            else:
                return True
        elif isplaymode == 1:
            #if RoomStateSync[channel]['roomgametype'] == '0' or RoomStateSync[channel]['roomgametype'] == '2':
            if dbresults[0] == '0' or dbresults[0] == '2':
                return False
            else:
                return True

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
    
    # Generate a random acronym.
    def generateacro(letters):
        lettercount = 0
        letterselect = ''
        while lettercount < letters:
            randletter = random.choice(string.ascii_uppercase)
            # If the selected letter is X or Z, there's a much lower chance of it actually being added.
            if randletter == 'X' or randletter == 'Z':
                if random.randint(0, 100) < 11:
                    addletter = 1
                else:
                    addletter = 0
            # For any other letter, just immediately add it.
            else:
                addletter = 1
            if addletter == 1:
                letterselect = letterselect + randletter
                lettercount += 1
        return letterselect
    
    # Get three random categories.
    def getcategories():
        database = sqlite3.connect('data/bezerk.db')
        dbcursor = database.cursor()
        dbcursor.execute('SELECT * FROM categories ORDER BY RANDOM() LIMIT 3')
        dbresults = dbcursor.fetchall()
        dbcursor.close()
        database.close()
        CategoryList = [dbresults[0][0], dbresults[1][0], dbresults[2][0]]
        return CategoryList
    
    # Give the time for the current voting round.
    def givevotingtime(playercount):
        playercount = int(playercount)
        VotingTime = 20
        # The time increases depending on the player count, up to a maximum of 45 seconds.
        if playercount > 4:
            VotingTime = 5 * playercount
        if playercount >= 9:
            VotingTime = 45
        return VotingTime
    
    #def calcvotewinner(RoomStateSync, GLChannel, AcroAnswers):
        #ivlcount = 1
        #voterlist = ''
        #RoomStateDB = sqlite3.connect('data/roomstate.db')
        #RSDBCursor = RoomStateDB.cursor()
        #RSDBCursor.execute('SELECT companswercount FROM ' + GLChannel)
        #dbresults = RSDBCursor.fetchone()
        #cmpcount = dbresults[0]
        ## Create the initial voter list.
        #print('CVW - creating initial list')
        ##while ivlcount < int(RoomStateSync[GLChannel]['companswercount']) + 1:
        #while ivlcount < int(cmpcount) + 1:
            #voterlist = voterlist + ',0'
            #ivlcount += 1
        #print('CVW - splitting list')
        #voterlist = voterlist.split(',')
        #votecount = 1
        #votewinner = ''
        #print('CVW - starting calculations')
        ##while votecount < int(RoomStateSync[GLChannel]['companswercount']) + 1:
        #while votecount < int(cmpcount) + 1:
            #nextvoter = AcroAnswers[votecount]
            ##voteindex = AcroAnswers.index(RoomStateSync['votedfor'][nextvoter])
            #RSDBCursor.execute('SELECT votedfor FROM round WHERE ircname = ?', (nextvoter,))
            #dbresults = RSDBCursor.fetchone()
            #voteindex = AcroAnswers.index(dbresults[0])
            #if voterlist[voteindex] != '':
                #highscore = int(voterlist[voteindex]) + 1
                #voterlist[voteindex] = str(highscore)
                #if votewinner == '':
                    #votewinner = AcroAnswers[voteindex]
                    #winnerindex = voteindex
                #elif highscore > int(voterlist[winnerindex]):
                    #votewinner = AcroAnswers[voteindex]
                    #winnerindex = voteindex
            #voteindex += 1
            #votecount += 1
            #print('CVW - loop')
        #RSDBCursor.close()
        #RoomStateDB.close()
        #return votewinner, voterlist
    
    def calcvotewinner(GLChannel):
        RoomStateDB = sqlite3.connect('data/roomstate.db')
        RSDBCursor = RoomStateDB.cursor()
        #RSDBCursor.execute('SELECT companswercount FROM ' + GLChannel)
        RSDBCursor.execute('SELECT playercount FROM ' + GLChannel)
        dbresults = RSDBCursor.fetchone()
        cmpcount = dbresults[0]
        RSDBCursor.execute('SELECT playerinfo FROM ' + GLChannel)
        dbresults = RSDBCursor.fetchone()
        plrlist = dbresults[0].split(',')
        votecount = 1
        votewinner = ''
        # Empty out the previous round scores.
        while votecount < int(cmpcount) + 1:
            RSDBCursor.execute('UPDATE round SET roundscore = 0 WHERE ircname = ?', (plrlist[votecount],))
            votecount += 1
        RoomStateDB.commit()
        votecount = 1
        # Calculate the current round scores.
        highscore = '0'
        votewinner = ''
        while votecount < int(cmpcount) + 1:
            RSDBCursor.execute('SELECT votedfor FROM round WHERE ircname = ?', (plrlist[votecount],))
            dbresults = RSDBCursor.fetchone()
            votedfor = dbresults[0]
            RSDBCursor.execute('SELECT roundscore FROM round WHERE ircname = ?', (votedfor,))
            dbresults = RSDBCursor.fetchone()
            if dbresults != None:
                newscore = str(dbresults[0] + 1)
                RSDBCursor.execute('UPDATE round SET roundscore = ? WHERE ircname = ?', (newscore, votedfor))
                #if votewinner == '':
                    #highscore = newscore
                    #votewinner = plrlist[votecount]
                #elif newscore > highscore:
                    #highscore = newscore
                    #votewinner = plrlist[votecount]
            votecount += 1
        RoomStateDB.commit()
        # Calculate the vote winner.
        RSDBCursor.execute('SELECT ircname, roomscore FROM player WHERE location = ? ORDER BY roomscore DESC LIMIT 14', (GLChannel,))
        dbresults = RSDBCursor.fetchall()
        vwltmp = []
        for player in dbresults:
            vwltmp.append(player[0])
        vwlist = []
        for player in vwltmp:
            RSDBCursor.execute('SELECT roundscore, ircname FROM round WHERE ircname = ?', (player,))
            dbresults = RSDBCursor.fetchone()
            vwlist.append(dbresults)
        vwlist.sort(reverse=True)
        # (In case everyone leaves before the voting round ends, check the player count as well.)
        RSDBCursor.execute('SELECT playercount FROM ' + GLChannel)
        dbresults = RSDBCursor.fetchone()
        votewinner = ''
        if int(dbresults[0]) > 0:
            votewinner = vwlist[0][1]
        if int(dbresults[0]) > 1 and vwlist[0][0] == vwlist[1][0]:
            RSDBCursor.execute('SELECT ircname, comptime FROM round WHERE ircname = ? OR ircname = ? ORDER BY comptime DESC LIMIT 2', (vwlist[0][1], vwlist[1][1]))
            dbresults = RSDBCursor.fetchall()
            if dbresults[1][1] < dbresults[0][1]:
                votewinner = dbresults[1][0]
        RSDBCursor.close()
        RoomStateDB.close()
        return votewinner
    
    # Choose three random ads to be in the ad break.
    def getinterstitials():
        with open('data/adlist.txt', 'r') as ads:
            adlist = []
            for ad in ads:
                ad = ad.strip()
                adlist.append(ad)
        adchoice1 = random.choice(adlist)
        adget = 0
        while adget != 1:
            adchoice2 = random.choice(adlist)
            if adchoice2 != adchoice1:
                adget = 1
        adget = 0
        while adget != 1:
            adchoice3 = random.choice(adlist)
            if adchoice3 != adchoice1 and adchoice3 != adchoice2:
                adget = 1
        adreturn = [adchoice1, adchoice2, adchoice3]
        return adreturn