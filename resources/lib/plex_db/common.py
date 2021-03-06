#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, unicode_literals

from .. import utils, variables as v

SUPPORTED_KODI_TYPES = (
    v.KODI_TYPE_MOVIE,
    v.KODI_TYPE_SHOW,
    v.KODI_TYPE_SEASON,
    v.KODI_TYPE_EPISODE,
    v.KODI_TYPE_ARTIST,
    v.KODI_TYPE_ALBUM,
    v.KODI_TYPE_SONG
)


class PlexDBBase(object):
    """
    Plex database methods used for all types of items
    """
    def __init__(self, cursor=None):
        # Allows us to use this class with a cursor instead of context mgr
        self.cursor = cursor

    def __enter__(self):
        self.plexconn = utils.kodi_sql('plex')
        self.cursor = self.plexconn.cursor()
        return self

    def __exit__(self, e_typ, e_val, trcbak):
        if e_typ:
            # re-raise any exception
            return False
        self.plexconn.commit()
        self.plexconn.close()

    def is_recorded(self, plex_id, plex_type):
        """
        FAST method to check whether a plex_id has already been recorded
        """
        self.cursor.execute('SELECT plex_id FROM %s WHERE plex_id = ?' % plex_type,
                            (plex_id, ))
        return self.cursor.fetchone() is not None

    def item_by_id(self, plex_id, plex_type=None):
        """
        Returns the item for plex_id or None.
        Supply with the correct plex_type to speed up lookup
        """
        answ = None
        if plex_type == v.PLEX_TYPE_MOVIE:
            answ = self.movie(plex_id)
        elif plex_type == v.PLEX_TYPE_EPISODE:
            answ = self.episode(plex_id)
        elif plex_type == v.PLEX_TYPE_SHOW:
            answ = self.show(plex_id)
        elif plex_type == v.PLEX_TYPE_SEASON:
            answ = self.season(plex_id)
        elif plex_type == v.PLEX_TYPE_SONG:
            answ = self.song(plex_id)
        elif plex_type == v.PLEX_TYPE_ALBUM:
            answ = self.album(plex_id)
        elif plex_type == v.PLEX_TYPE_ARTIST:
            answ = self.artist(plex_id)
        else:
            # SLOW - lookup plex_id in all our tables
            for kind in (v.PLEX_TYPE_MOVIE,
                         v.PLEX_TYPE_EPISODE,
                         v.PLEX_TYPE_SHOW,
                         v.PLEX_TYPE_SEASON,
                         'song',  # darn
                         v.PLEX_TYPE_ALBUM,
                         v.PLEX_TYPE_ARTIST):
                method = getattr(self, kind)
                answ = method(plex_id)
                if answ:
                    break
        return answ

    def item_by_kodi_id(self, kodi_id, kodi_type):
        """
        """
        if kodi_type not in SUPPORTED_KODI_TYPES:
            return
        self.cursor.execute('SELECT * from %s WHERE kodi_id = ? LIMIT 1'
                            % v.PLEX_TYPE_FROM_KODI_TYPE[kodi_type],
                            (kodi_id, ))
        method = getattr(self, 'entry_to_%s' % v.PLEX_TYPE_FROM_KODI_TYPE[kodi_type])
        return method(self.cursor.fetchone())

    def plex_id_by_last_sync(self, plex_type, last_sync):
        """
        Returns an iterator for all items where the last_sync is NOT identical
        """
        return (x[0] for x in
                self.cursor.execute('SELECT plex_id FROM %s WHERE last_sync <> ?' % plex_type,
                                    (last_sync, )))

    def checksum(self, plex_id, plex_type):
        """
        Returns the checksum for plex_id
        """
        self.cursor.execute('SELECT checksum FROM %s WHERE plex_id = ? LIMIT 1' % plex_type,
                            (plex_id, ))
        try:
            return self.cursor.fetchone()[0]
        except TypeError:
            pass

    def update_last_sync(self, plex_id, plex_type, last_sync):
        """
        Sets a new timestamp for plex_id
        """
        self.cursor.execute('UPDATE %s SET last_sync = ? WHERE plex_id = ?' % plex_type,
                            (last_sync, plex_id))

    def remove(self, plex_id, plex_type):
        """
        Removes the item from our Plex db
        """
        self.cursor.execute('DELETE FROM %s WHERE plex_id = ?' % plex_type, (plex_id, ))

    def every_plex_id(self, plex_type):
        """
        Returns an iterator for plex_type for every single plex_id
        """
        return (x[0] for x in
                self.cursor.execute('SELECT plex_id from %s' % plex_type))

    def missing_fanart(self, plex_type):
        """
        Returns an iterator for plex_type for all plex_id, where fanart_synced
        has not yet been set to 1
        """
        return (x[0] for x in
                self.cursor.execute('SELECT plex_id from %s WHERE fanart_synced = 0' % plex_type))

    def set_fanart_synced(self, plex_id, plex_type):
        """
        Toggles fanart_synced to 1 for plex_id
        """
        self.cursor.execute('UPDATE %s SET fanart_synced = 1 WHERE plex_id = ?' % plex_type,
                            (plex_id, ))

    def plexid_by_sectionid(self, section_id, plex_type):
        return (x[0] for x in
                self.cursor.execute('SELECT plex_id FROM %s WHERE section_id = ?' % plex_type,
                                    (section_id, )))

    def kodiid_by_sectionid(self, section_id, plex_type):
        return (x[0] for x in
                self.cursor.execute('SELECT kodi_id FROM %s WHERE section_id = ?' % plex_type,
                                    (section_id, )))


def initialize():
        """
        Run once upon PKC startup to verify that plex db exists.
        """
        with PlexDBBase() as plexdb:
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS version(
                    idVersion TEXT)
            ''')
            plexdb.cursor.execute('''
                INSERT OR REPLACE INTO version(idVersion)
                VALUES (?)
            ''', (v.ADDON_VERSION, ))
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS sections(
                    section_id INTEGER PRIMARY KEY,
                    section_name TEXT,
                    plex_type TEXT,
                    kodi_tagid INTEGER,
                    sync_to_kodi INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS movie(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    kodi_id INTEGER,
                    kodi_fileid INTEGER,
                    kodi_pathid INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS show(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    kodi_id INTEGER,
                    kodi_pathid INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS season(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    show_id INTEGER,
                    parent_id INTEGER,
                    kodi_id INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS episode(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    show_id INTEGER,
                    grandparent_id INTEGER,
                    season_id INTEGER,
                    parent_id INTEGER,
                    kodi_id INTEGER,
                    kodi_fileid INTEGER,
                    kodi_pathid INTEGER,
                    fanart_synced INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS artist(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    kodi_id INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS album(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    artist_id INTEGER,
                    parent_id INTEGER,
                    kodi_id INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS track(
                    plex_id INTEGER PRIMARY KEY,
                    checksum INTEGER UNIQUE,
                    section_id INTEGER,
                    artist_id INTEGER,
                    grandparent_id INTEGER,
                    album_id INTEGER,
                    parent_id INTEGER,
                    kodi_id INTEGER,
                    kodi_pathid INTEGER,
                    last_sync INTEGER)
            ''')
            plexdb.cursor.execute('''
                CREATE TABLE IF NOT EXISTS playlists(
                    plex_id INTEGER PRIMARY KEY,
                    plex_name TEXT,
                    plex_updatedat INTEGER,
                    kodi_path TEXT,
                    kodi_type TEXT,
                    kodi_hash TEXT)
            ''')
            # DB indicees for faster lookups
            commands = (
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_movie_1 ON movie (plex_id)',
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_show_1 ON show (plex_id)',
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_season_1 ON season (plex_id)',
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_episode_1 ON episode (plex_id)',
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_artist_1 ON artist (plex_id)',
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_album_1 ON album (plex_id)',
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_track_1 ON track (plex_id)',
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_playlists_1 ON playlists (plex_id)',
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_playlists_2 ON playlists (kodi_path)',
                'CREATE UNIQUE INDEX IF NOT EXISTS ix_playlists_3 ON playlists (kodi_hash)',
            )
            for cmd in commands:
                plexdb.cursor.execute(cmd)


def wipe():
    """
    Completely resets the Plex database
    """
    with PlexDBBase() as plexdb:
        plexdb.cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = [i[0] for i in plexdb.cursor.fetchall()]
        for table in tables:
            plexdb.cursor.execute('DROP table IF EXISTS %s' % table)
