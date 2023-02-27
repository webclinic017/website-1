
import simplejson

from sqlobject import *

# Replace this with the URI for your actual database
connection = connectionForURI('sqlite:/:memory:')
sqlhub.processConnection = connection

class Song(SQLObject):

    name = StringCol()
    artist = StringCol()
    album = StringCol()

# Create fake data for demo - this is not needed for the real thing
def MakeFakeDB():
    Song.createTable()
    s1 = Song(name="B Song",
              artist="Artist1",
              album="Album1")
    s2 = Song(name="A Song",
              artist="Artist2",
              album="Album2")

def Main():
    # This is an iterable, not a list
    all_songs = Song.select().orderBy(Song.q.name)

    songs_as_dict = []

    for song in all_songs:
        song_as_dict = {
            'name' : song.name,
            'artist' : song.artist,
            'album' : song.album}
        songs_as_dict.append(song_as_dict)

    print(simplejson.dumps(songs_as_dict))


if __name__ == "__main__":
    MakeFakeDB()
    Main()