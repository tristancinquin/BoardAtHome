# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.http import  HttpResponse, Http404
from django.shortcuts import render
from django.db import connection
from django.urls import resolve
import unicodedata
from django.http import HttpResponseRedirect


def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]

def get_games_sql():
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM games WHERE Name NOT NULL;")
        games_rows = dictfetchall(cursor)	#[{'Game_ID': 1, 'Description': "...", Image:"...", ...}, {'Game_ID': 2, 'Description': "...", Image:"..."}...]
    return games_rows

def get_game_sql(game_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM games WHERE Game_ID=" + str(game_id) + ";")
        game_rows = dictfetchall(cursor)	#[{'Game_ID': 1, 'Description': "...", Image:"...", ...}, {'Game_ID': 2, 'Description': "...", Image:"..."}...]
    return game_rows[0]

def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = nfkd_form.encode('ASCII', 'ignore')
    return only_ascii

def index(request):
    games = get_games_sql()
    return render(request, 'Game/index.html', {'games': games})

def detail(request, game_id):
    game = get_game_sql(game_id)
    game_avg = get_average_rating(game_id)
    if not game:
        raise Http404("Game does not exist")
    return render(request, "Game/detail.html", {'game': game, 'user': request.user, 'game_avg': game_avg})

def get_game_user_relation(user_id, game_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM Relation WHERE Game_ID=" + str(game_id) + " AND User_ID=" + str(user_id) +";")
        game_rows = dictfetchall(cursor)	#[{'Game_ID': 1, 'Description': "...", Image:"...", ...}, {'Game_ID': 2, 'Description': "...", Image:"..."}...]
    return game_rows

def add_to_wishlist(request, game_id):
    print (request.user.id)
    game = get_game_sql(game_id)
    with connection.cursor() as cursor:
        result = get_game_user_relation(request.user.id, game_id)
        if not result:
            cursor.execute("INSERT INTO Relation(Game_ID, User_ID, Wishlist) VALUES("
                               + str(game_id) + "," + str(request.user.id) + ", True);")
        else:
            cursor.execute("UPDATE Relation SET Wishlist=true WHERE User_ID="
                           + str(request.user.id) + " AND Game_ID="+str(game_id))
        print("Succes")

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'), {'game': game, 'user': request.user})

def add_to_ownedlist(request, game_id):
    print (request.user.id)
    game = get_game_sql(game_id)
    with connection.cursor() as cursor:
        result = get_game_user_relation(request.user.id, game_id)
        if not result:
            cursor.execute("INSERT INTO Relation(Game_ID, User_ID, Owned) VALUES("
                           + str(game_id) + "," + str(request.user.id) + ", True);")
        else:
            cursor.execute("UPDATE Relation SET Owned=true WHERE User_ID="
                           + str(request.user.id) + " AND Game_ID=" + str(game_id))
        print("Succes")
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'), {'game': game, 'user': request.user})

def add_rating(request, game_id, score):
    print ("add rating called")
    game = get_game_sql(game_id)
    with connection.cursor() as cursor:
        result = get_game_user_relation(request.user.id, game_id)
        if not result:
            cursor.execute("INSERT INTO Relation(Game_ID, User_ID, Score) VALUES("
                           + str(game_id) + "," + str(request.user.id) + ", " + str(score) + ");")
        else:
            cursor.execute("UPDATE Relation SET Score=" + str(score) + " WHERE User_ID="
                           + str(request.user.id) + " AND Game_ID=" + str(game_id))
        print("Succes")
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'), {'game': game, 'user': request.user})

def get_average_rating(game_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT avg(Score) FROM Relation WHERE Game_ID=" + str(game_id))
        result = cursor.fetchall()
    return result[0][0]