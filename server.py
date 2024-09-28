import asyncio
import argparse
import aiohttp
import re 
import time
import json

#------------------A Bunch of Constants------------------#
# Google API Key
API_KEY = "YOUR_API_KEY"
# Base URL for Google Places API
BASE_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
# Servers mapped to their respective ports
SERVERS = {
    "Bailey" : 10000,
    "Bona" : 10001,
    "Campbell" : 10002,
    "Clark" : 10003,
    "Jaquez" : 10004
}
# Servers mapped to their respective connections
CONNECTIONS = {
    "Bailey" : ["Bona", "Campbell"],
    "Bona" : ["Bailey", "Campbell", "Clark"],
    "Campbell" : ["Bailey", "Bona", "Jaquez"],
    "Clark" : ["Bona", "Jaquez"],
    "Jaquez" : ["Bona", "Campbell", "Clark"]
}
#--------------------------------------------------------#
class Server:                                            
    def __init__(self, server_name):                     #Server class to handle all server related operations
        self.name = server_name                          #Name of the server
        self.port = SERVERS[server_name]                 #Port of the server given by dictionary
        self.connections = CONNECTIONS[server_name]      #Connections of the server given by dictionary
        self.locations = {}                              #Locations of people connected to the server... example: kiwi.cs.ucla.edu    
                               
    async def handle_AT(self, response):
        print("Handling AT")
        if response is not None:
            message = response.split()
            if not message[3] in self.locations or self.locations.get(message[3])[4] != response[4]: #NOTE: indexed at 4 to check if the location has been updated
                self.locations[message[3]] = response
                for server in self.connections:
                    try:
                        _, writer = await asyncio.open_connection('127.0.0.1', SERVERS[server])     #At this point the AT handler should be called for each connect server that recieves the message
                        writer.write(response.encode())
                        await writer.drain()
                        writer.close()
                        await writer.wait_closed() 
                    except:
                        pass            
            else:
                print("Duplicate message")
                return response
        else:
            return None
        
    async def handle_IAMAT(self, data): 
        print("Handling IAMAT...")
        message = data.split()
        client_time = float(message[3])
        server_time = time.time()
        clock_diff = server_time - client_time                                          #Calculate the clock skew
        part_to_send = message[1] + " " + message[2] + " " + message[3]
        response = str("AT " + self.name + " +" + str(clock_diff) + " " + part_to_send) #Format the response
        self.locations[message[1]] = response
        for server in self.connections:    
            try:                                                                        #Send the response to all connected servers
                _, writer = await asyncio.open_connection('127.0.0.1', SERVERS[server]) #At this point the AT handler should be called for each connect server that recieves the message
                writer.write(response.encode())
                await writer.drain()
                writer.close()
                await writer.wait_closed() 
            except:
                pass
        print("IAMAT response: " + response)
        return str(response  + '\n')
    
    async def handle_WHATSAT(self, data):
        print("Handling WHATSAT...")
        message = data.split()                           #Split the message into a list
        client = message[1]                              #Get the client name                                     
        result_count = int(message[3])                   #Get the number of results to return
        print(self.locations.get(client))
        if self.locations.get(client) is None:
            print("Client not found")
            return str("? " + data)
        latest_update = self.locations[client]           #Get the latest location of the client
        print(latest_update)
        curr_location = latest_update.split()[4]         #Pulls latitude and longitude from the latest location
        temp = re.split('(\+|-)', curr_location)         #Splits the latitude and longitude into a list
        latitude = temp[1] + temp[2]
        longitude = temp[3] + temp[4]
        location = latitude + "%2C" + longitude
        radius = int(message[2]) * 1000 
        if radius < 0:
            print("Invalid radius")
            return str("? " + data)
        request = BASE_URL + "location=" + location + "&radius=" + str(radius) + "&key=" + API_KEY
        async with aiohttp.ClientSession() as session:
            async with session.get(request) as response:
                api_resp = await response.json()
                if len(api_resp['results']) > result_count:
                    api_resp['results'] = api_resp['results'][:result_count]
                return str(latest_update + '\n' + json.dumps(api_resp, indent=4) + '\n\n')  

    async def begin_server(self, reader, writer):
        print("Connected to client...")
        try:
            data = await reader.read(100)
            if data is not None:
                message = data.decode()
                command = message.split()[0]
                if command == "IAMAT" and len(message.split()) == 4:
                    result = await self.handle_IAMAT(message)
                    if result is not None:
                        writer.write(result.encode())
                elif command == "WHATSAT" and len(message.split()) == 4:
                    result = await self.handle_WHATSAT(message)
                    if result is not None:
                        writer.write(result.encode())
                elif command == "AT" and len(message.split()) == 6:
                    result = await self.handle_AT(message)
                    if result is not None:
                        writer.write(result.encode())
                else:
                    writer.write(("? " + message).encode())
        except:
            print("Disconnected from client...")
            pass
        await writer.drain()
        writer.close()
        await writer.wait_closed()

async def main():
    parser = argparse.ArgumentParser(description="Server for the chat application")
    parser.add_argument("server", type=str, help="The server to connect to")
    args = parser.parse_args()
    server = args.server
    if server in SERVERS:
        try:
            herd = Server(server)
            print("Starting server...")
            asyncio_server = await asyncio.start_server(herd.begin_server, '127.0.0.1', SERVERS[server])
            async with asyncio_server:
                await asyncio_server.serve_forever()
        except KeyboardInterrupt:
            print("Server shutting down...")
            pass
    else:
        print("Invalid server")        
                           
if __name__ == "__main__":
    asyncio.run(main())

