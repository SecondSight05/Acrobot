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
        RoomState = ConfigParser()
        RoomState.read('data/roomstate.ini')
        RoomState['playerloc'] = {}
        RoomState['playername'] = {}
        RoomState['playerfmf'] = {}
        RoomState['playeronline'] = {}
        RoomState['playerinroom'] = {}
        RoomStateSync = ConfigParser()
        RoomStateSync.read('data/roomstate_sync.ini')
        RoomStateSync['comptime'] = {}
        
        # Setup the Find My Friends RoomState key for each player
        database = sqlite3.connect('data/bezerk.db')
        dbcursor = database.cursor()
        dbcursor.execute('SELECT * FROM accounts')
        for player in dbcursor:
            RoomState['playeronline'][player[0]] = '0'
        
        # Setup the RoomState keys for each room
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
        dbcursor.close()
        database.close()
        
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
                    IRCSock.send('JOIN #Acro_List\n'.encode())
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
                    JoinIRCName = JoinMessage[1].split('!')
                    JoinIRCName = JoinIRCName[0]
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
                    RoomState['playerloc'][LogonIRCName] = LogonChannel[1:]
                    RoomState['playername'][LogonIRCName] = LogonMessage[1]
                    RoomState['playerfmf'][LogonMessage[1]] = LogonIRCName
                    RoomState['playeronline'][LogonMessage[1]] = '1'
                    RoomState['playerinroom'][LogonIRCName] = '0'
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
                            # TBD: properly add the high score counter
                            RoomPlayerCount = int(RoomState[room[1]]['roomplayercount'])
                            RoomHighScore = int(RoomState[room[1]]['roomhighscore'])
                            RoomMode = RoomState[room[1]]['roommode']
                            IRCSock.send(f'PRIVMSG {LogonIRCName} :list_item bot 0 "{room[0]}" 0 "{IRCLocation}" {IRCPort} 0 "{room[1]}" 0 "Acrobot" {room[2]} "{RoomMode}" {str(RoomPlayerCount)} {str(RoomHighScore)} 0 {room[3]}\r\n'.encode())
                        dbcursor.close()
                        database.close()
                        IRCSock.send('PRIVMSG {} :end_list bot\r\n'.format(LogonIRCName).encode())
            
            # Set the player up for starting the actual game.
            elif msg.find('start_play'.encode()) != -1:
                StartPlayIRCName = msg[1:25].decode('UTF-8')
                StartPlayIRCName = StartPlayIRCName.split('!')
                StartPlayIRCName = StartPlayIRCName[0]
                # Get the room's name and current state.
                StartPlayChannel = RoomState['playerloc'][StartPlayIRCName]
                StartPlayRoomState = RoomStateSync[StartPlayChannel]['roomcurrentstate']
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
                StartPlayUsername = RoomState['playername'][StartPlayIRCName]
                # Send the welcome message to the player privately.
                IRCSock.send('PRIVMSG {} :chat "Welcome to {}"\r\n'.format(StartPlayIRCName, StartPlayRoomName).encode())
                # Send the player join message to the room publicly.
                IRCSock.send('PRIVMSG #{} :player add "{}" 0 "{}"\r\n'.format(StartPlayChannel, StartPlayIRCName, StartPlayUsername).encode())
                # Check if there isn't anyone else in the room.
                RoomPlayerCount = int(RoomState[StartPlayChannel]['roomplayercount'])
                if RoomPlayerCount > 0:
                    # If false, send the info for the other players to the new player privately.
                    listplayeradd = 1
                    listplayerinfo = RoomState[StartPlayChannel]['roomplayerinfo'].split('/')
                    while listplayeradd <= RoomPlayerCount:
                        listplayeritem = listplayerinfo[listplayeradd].split(',')
                        ListPlayerIRCName = listplayeritem[0]
                        ListPlayerScore = listplayeritem[1]
                        ListPlayerUsername = listplayeritem[2]
                        IRCSock.send('PRIVMSG {} :player add "{}" {} "{}"\r\n'.format(StartPlayIRCName, ListPlayerIRCName, ListPlayerScore, ListPlayerUsername).encode())
                        listplayeradd += 1
                # Update the room info to show a new player.
                RoomState[StartPlayChannel]['roomplayercount'] = str(int(RoomState[StartPlayChannel]['roomplayercount']) + 1)
                RoomHighScore = int(RoomState[StartPlayChannel]['roomhighscore'])
                RoomMode = RoomState[StartPlayChannel]['roommode']
                RoomState[StartPlayChannel]['roomplayerinfo'] = RoomState[StartPlayChannel]['roomplayerinfo'] + '/' +  StartPlayIRCName + ',0,' + StartPlayUsername
                RoomState['playerinroom'][StartPlayIRCName] = '1'
                # Set the game type (Play or Practice) if that game type isn't already running, and a certain amount of players are in the room.
                if RoomStateSync[StartPlayChannel]['roomgametype'] == '0':
                    # Practice Mode
                    if RoomState[StartPlayChannel]['roomplayercount'] == '1' or RoomState[StartPlayChannel]['roomplayercount'] == '2':
                        RoomState[StartPlayChannel]['roommode'] = 'Practice'
                        RoomStateSync[StartPlayChannel]['roomgametype'] = '2'
                        with open('data/roomstate_sync.ini', 'w') as rssync:
                            RoomStateSync.write(rssync)
                        IRCSock.send('PRIVMSG {} :chat "There must be at least 3 players to start a game - You will be in Practice mode until then."\r\n'.format(StartPlayIRCName).encode())
                        threading.Thread(target=GameLoop.practice, args=(IRCSock, RoomStateSync, StartPlayChannel)).start()
                elif RoomStateSync[StartPlayChannel]['roomgametype'] == '2':
                    # Play Mode
                    if int(RoomState[StartPlayChannel]['roomplayercount']) >= 3:
                        RoomState[StartPlayChannel]['roommode'] = 'Play'
                        RoomStateSync[StartPlayChannel]['roomgametype'] = '1'
                        with open('data/roomstate_sync.ini', 'w') as rssync:
                            RoomStateSync.write(rssync)
                        IRCSock.send('PRIVMSG #{} :chat "A third player has joined - Get ready to play!"\r\n'.format(StartPlayChannel).encode())
                        threading.Thread(target=GameLoop.play, args=(IRCSock, RoomStateSync, StartPlayChannel)).start()
                # Update the room in the list to show a new player.
                IRCSock.send('PRIVMSG #Acro_List :start_list bot\r\n'.encode())
                IRCSock.send(f'PRIVMSG #Acro_List :list_item bot 0 "{dbresults[0]}" 0 "{IRCLocation}" {IRCPort} 0 "{dbresults[1]}" 0 "Acrobot" {dbresults[2]} "{RoomMode}" {str(RoomPlayerCount)} {str(RoomHighScore)} 0 {dbresults[3]}\r\n'.encode())
                IRCSock.send('PRIVMSG #Acro_List :end_list bot\r\n'.encode())
            
            # Logoff - Remove player from room.
            elif msg.find('logoff ip'.encode()) != -1 or msg.find('QUIT'.encode()) != -1:
                LogoffIRCName = msg[1:25].decode('UTF-8')
                LogoffIRCName = LogoffIRCName.split('!')
                LogoffIRCName = LogoffIRCName[0]
                if RoomState['playerloc'][LogoffIRCName].find('Acro_List') == -1 and RoomState['playerinroom'][LogoffIRCName] == '1':
                    # Get the channel that the player is in.
                    LogoffChannel = RoomState['playerloc'][LogoffIRCName]
                    # Find the other two pieces of info from RoomState.
                    logoffinfo = RoomState[LogoffChannel]['roomplayerinfo'].split('/')
                    for loitem in logoffinfo:
                        if loitem != '':
                            if loitem.find(LogoffIRCName) != -1:
                                loitem = loitem.split(',')
                                LogoffScore = loitem[1]
                                LogoffUsername = loitem[2]
                                IRCLog.info('Username ' + LogoffUsername + ' logged off of the #' + LogoffChannel + ' room')
                    # Get the index for the player's info in RoomState.
                    LogoffIndex = logoffinfo.index(LogoffIRCName + ',' + LogoffScore + ',' + LogoffUsername)
                    # Remove the player from the room in RoomState.
                    logoffinfo.pop(LogoffIndex)
                    logoffinfo = '/'.join(logoffinfo)
                    RoomState[LogoffChannel]['roomplayercount'] = str(int(RoomState[LogoffChannel]['roomplayercount']) - 1)
                    RoomState['playeronline'][LogoffUsername] = '0'
                    RoomState['playerinroom'][LogoffIRCName] = '0'
                    # Update the in-game player list.
                    IRCSock.send('PRIVMSG #{} :player remove "{}" {} "{}"\r\n'.format(LogoffChannel, LogoffIRCName, LogoffScore, LogoffUsername).encode())
                    # Check if the room's game type needs to be changed.
                    if RoomStateSync[LogoffChannel]['roomgametype'] == '2':
                        if int(RoomState[LogoffChannel]['roomplayercount']) == 0:
                            # If there are no players left, close the loop for that room.
                            RoomStateSync[LogoffChannel]['roomgametype'] = '0'
                            RoomState[LogoffChannel]['roommode'] = ''
                            with open('data/roomstate_sync.ini', 'w') as rssync:
                                RoomStateSync.write(rssync)
            
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
                    if RoomState['playeronline'][FMFUsername] == '0' or dbresults is None:
                        dbcursor.close()
                        database.close()
                        # If they aren't, send player_not_found.
                        IRCSock.send('PRIVMSG {} :player_not_found "{}"\r\n'.format(FMFIRCName, FMFUsername).encode())
                    else:
                        # Otherwise, check if the requested player is in #Acro_List.
                        FMFIRCReq = RoomState['playerfmf'][FMFUsername]
                        if RoomState['playerloc'][FMFIRCReq].find('Acro_List') != -1:
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
                            FMFChannel = RoomState['playerloc'][FMFIRCReq]
                            dbcursor.execute('SELECT RoomName, IsClean FROM rooms WHERE ChannelName = ?', (FMFChannel,))
                            dbresults = dbcursor.fetchone()
                            fmfroomname = dbresults[0]
                            fmfisclean = str(dbresults[1])
                            dbcursor.close()
                            database.close()
                            RoomPlayerCount = RoomState[FMFChannel]['roomplayercount']
                            RoomHighScore = RoomState[FMFChannel]['roomhighscore']
                            RoomMode = RoomState[FMFChannel]['roommode']
                            FMFRoomList = '0'
                        IRCSock.send(f'PRIVMSG {FMFIRCName} :player_found "{FMFUsername}" "{fmfroomname}" 0 "{IRCLocation}" {IRCPort} 0 "{FMFChannel}" 0 "Acrobot" {fmfisclean} "{RoomMode}" {RoomPlayerCount} {RoomHighScore} {FMFRoomList}\r\n'.encode())
            
            # When someone registers a new account, add the fact that they're not online yet to RoomState.
            elif msg.find('newreg'.encode()) != -1:
                newreg = msg.decode('UTF-8')
                newreg = newreg.split(' ')
                newreg = newreg[4].split('\r\n')
                newreg = newreg[0]
                RoomState['playeronline'][newreg] = '0'
                IRCSock.send('PRIVMSG NPLink :npdone\r\n'.encode())
            
            # When an acro is sent during the composition round.
            elif msg.find('response answer'.encode()) != -1:
                RAAcro = msg.decode('UTF-8')
                RAAcro = RAAcro.split('"')
                RATime = RAAcro[0].split(' ')
                RAAcro = RAAcro[1]
                RAPlayer = RATime[6]
                RATime = RATime[5]
                rsch = RoomState['playerloc'][RAPlayer]
                RoomStateSync[rsch]['companswers'] = RoomStateSync[rsch]['companswers'] + '/' + RoomStateSync[rsch]['companswercount'] + ',' + RAPlayer + ',' + RAAcro
                RoomStateSync[rsch]['companswercount'] = str(int(RoomStateSync[rsch]['companswercount']) + 1)
                RoomStateSync['comptime'][RAPlayer] = str(RATime)
                with open('data/roomstate_sync.ini', 'w') as rssync:
                    RoomStateSync.write(rssync)
                IRCSock.send('PRIVMSG #{} :answer_received {}\r\n'.format(rsch, RoomStateSync[rsch]['companswercount']).encode())
            
            # TBD: voting responses
            elif msg.find('response vote'.encode()) != -1:
                print('voting round TBD')
            
            # When a category is selected by the winning player.
            elif msg.find('response category'.encode()) != -1:
                RCCategory = msg.decode('UTF-8')
                RCCategory = RCCategory.split(' ')
                RCPlayer = RCCategory[0].split('!')
                RCCategory = RCCategory[5]
                RCPlayer = RCPlayer[0].split(':')
                RCPlayer = RCPlayer[1]
                RoomStateSync[RoomState['playerloc'][RCPlayer]]['category'] = RCCategory
                with open('data/roomstate_sync.ini', 'w') as rssync:
                    RoomStateSync.write(rssync)

class GameLoop():
    def practice(IRCSock, RoomStateSync, GLChannel):
        AcroLetters = 3
        AcroCategory = 'General Acrophobia'
        PracticeLoop = True
        PracticeLoop = GameLoop.loopcheck_pr(GLChannel, RoomStateSync)
        time.sleep(4)
        while PracticeLoop is True:
            # Composition Round (Practice)
            IRCSock.send('PRIVMSG #{} :start_comp_round 2500 60000 1 "{}" "{}"\r\n'.format(GLChannel, Acrophobia.generateacro(AcroLetters), AcroCategory).encode())
            PracticeLoop = GameLoop.loopcheck_pr(GLChannel, RoomStateSync)
            time.sleep(78)
            # If there wasn't any composition round submissions, skip the category picker round.
            if int(RoomStateSync[GLChannel]['companswercount']) > 0:
                # In Practice Mode, the first person to submit an acro chooses the category.
                CategoryChooser = RoomStateSync[GLChannel]['companswers'].split(',')
                CategoryChooser = CategoryChooser[1]
                # Category Picker Round (Practice)
                IRCSock.send('PRIVMSG #{} :start_categories 2500 5000 1 "{}"\r\n'.format(GLChannel, CategoryChooser).encode())
                PracticeLoop = GameLoop.loopcheck_pr(GLChannel, RoomStateSync)
                # Get the categories and show them to the player.
                CategoryList = Acrophobia.getcategories()
                IRCSock.send('PRIVMSG #{} :start_list category\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :list_item category 0 "{}"\r\n'.format(GLChannel, CategoryList[0]).encode())
                IRCSock.send('PRIVMSG #{} :list_item category 1 "{}"\r\n'.format(GLChannel, CategoryList[1]).encode())
                IRCSock.send('PRIVMSG #{} :list_item category 2 "{}"\r\n'.format(GLChannel, CategoryList[2]).encode())
                IRCSock.send('PRIVMSG #{} :list_item category 3 "General Acrophobia"\r\n'.format(GLChannel).encode())
                IRCSock.send('PRIVMSG #{} :end_list category\r\n'.format(GLChannel).encode())
                PracticeLoop = GameLoop.loopcheck_pr(GLChannel, RoomStateSync)
                time.sleep(10)
                # If the bottom category or no category is chosen, set the next category to General Acrophobia.
                if RoomStateSync[GLChannel]['category'] == '' or RoomStateSync[GLChannel]['category'] == '3':
                    AcroCategory = 'General Acrophobia'
                # Otherwise, set the category to the one that was chosen.
                else:
                    AcroCategory = CategoryList[int(RoomStateSync[GLChannel]['category'])]
            # Increase the amount of letters in the next acronym by one. If it's over 7, set it back to 3.
            AcroLetters += 1
            if AcroLetters > 7:
                AcroLetters = 3
            # Empty out the composition round answers.
            RoomStateSync[GLChannel]['companswers'] = ''
            RoomStateSync[GLChannel]['companswercount'] = '0'
            RoomStateSync[GLChannel]['category'] = ''
            with open('data/roomstate_sync.ini', 'w') as rssync:
                RoomStateSync.write(rssync)
            PracticeLoop = GameLoop.loopcheck_pr(GLChannel, RoomStateSync)
    
    def play(IRCSock, RoomStateSync, GLChannel):
        # TBD: the rest of this
        IRCSock.send('PRIVMSG #{} :start_game 8250\r\n'.format(GLChannel).encode())
    
    def loopcheck_pr(channel, RoomStateSync):
        if RoomStateSync[channel]['roomgametype'] == '0' or RoomStateSync[channel]['roomgametype'] == '1':
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