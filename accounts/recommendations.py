import numpy as np
from django.db import connection
from operator import itemgetter
from django.shortcuts import render
from sklearn.neighbors import NearestNeighbors

# Returns a dict {"CategoryName" : avg rating in category} for each game in a users wishlist, owned list or liked list
def category_avg_rating_map(cursor):
    categories = {}
    counts = {}
    for row in cursor.fetchall():
        for e in row[0].split(","):
            if e in categories:
                counts[e] += 1
                categories[e] += row[1]
            else:
                counts[e] = 1
                categories[e] = row[1]
    for category in categories:
        categories[category] /= counts[category]
    return categories # Returns dict {"CategoryName" : avg rating in category}

# Vector with category name - index mapping used to for feature construction
def get_category_mapping():
    with connection.cursor() as cursor:
        cursor.execute("SELECT Category FROM games WHERE Name NOT NULL;")
        categories = set()
        for row in cursor.fetchall():
            for e in row[0].split(","):
                categories.add(e)
        cursor.close()
        return {v:k for k, v in enumerate(categories)} # Returns dict {"CategoryName" : index}

# Returns a vector v containing the average score of the games in a users wishlist, owned list or liked list of a given
# category. Component v_i denotes the average score of the games of category at index i in category mapping for a specfic
# user
def get_user_category_vector(userID):
    with connection.cursor() as cursor:
        cursor.execute( "SELECT g1.Category, g2.Score " +
                        "FROM games g1, " +
                            "(SELECT Game_ID, Score From Relation " +
                            "Where User_ID=" + str(userID) + " AND Score NOT NULL) g2 " +
                        "WHERE g1.Name NOT NULL AND g1.Game_ID = g2.Game_ID;")
        user_categories_rating = category_avg_rating_map(cursor) # dict {"CategoryName" : avg rating in category}
        category_mapping = get_category_mapping() # dict {"CategoryName" : index}
        category_vector = np.zeros(len(category_mapping))
        for category in user_categories_rating:
            category_vector[category_mapping[category]] = user_categories_rating[category]
        cursor.close()
        return np.array(category_vector)


def get_game_category_vector_recommendations(game_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT Category, Rating FROM games WHERE Name NOT NULL AND Game_ID= " + str(game_id) + ";")
        game_category_vectors = []
        category_mapping = get_category_mapping()  # dict {"CategoryName" : index}
        v_len = len(category_mapping)
        rows = cursor.fetchall()
        max_score = max(rows, key=itemgetter(1))[1]
        for row in rows:
            category_vector = np.zeros(v_len)
            for category in row[0].split(","):
                category_vector[category_mapping[category]] += 1
            category_vector *= row[1] / float(max_score)
        cursor.close()
        return np.array(category_vector)

# In database creates table Game_Category_Vectors that contains the item based game category vectors
def create_table_game_category_vector():
    with connection.cursor() as cursor:
        cursor.execute("SELECT Category, Rating FROM games WHERE Name NOT NULL;")
        game_category_vectors = []
        category_mapping = get_category_mapping() # dict {"CategoryName" : index}
        v_len = len(category_mapping)
        max_score = max(cursor.fetchall(), key=itemgetter(1))[1]
        cursor.execute("SELECT Category, Rating FROM games WHERE Name NOT NULL;")
        for row in cursor.fetchall():
            category_vector = np.zeros(v_len)
            for category in row[0].split(","):
                category_vector[category_mapping[category]] += 1
            category_vector *= row[1] / float(max_score)                 # pas sur que reduction de taille soit necessaire
            game_category_vectors.append(np.array(category_vector))
        game_category_vectors = np.array(game_category_vectors)
        query = ""
        for i in range(v_len):
            if i != v_len-1:
                query += "id" + str(i) + " FLOAT, "
            else:
                query += "id" + str(i) + " FLOAT"
        cursor.execute("Create Table Game_Category_Vectors (" + query + ");")
        for i in range(len(game_category_vectors)): # for all games
            query = "("
            for j in range(len(game_category_vectors[0])): # for all categories
                if j == len(game_category_vectors[0]) - 1:
                    query += str(game_category_vectors[i][j])
                else:
                    query += str(game_category_vectors[i][j]) + ", "
            query += ");"
            cursor.execute("Insert Into Game_Category_Vectors Values " + query)
        cursor.close()
        return np.array(game_category_vectors)

# Read game category vectors in databaase
def get_game_category_vectors():
    with connection.cursor() as cursor:
        game_category_vectors = []
        cursor.execute("SELECT * FROM Game_Category_Vectors;")
        for row in cursor.fetchall():
            game_category_vectors.append(np.array(row))
        return np.array(game_category_vectors)

def get_all_users_category_vectors():
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT User_ID FROM Relation WHERE Score NOT NULL;")
        count = cursor.fetchall()
        vectors = []
        for i in count:
            print (i)
            vectors.append(np.array(np.hstack([get_user_category_vector(i[0]), i[0]]))) # append user_id to category vector
        cursor.close()
        return np.array(vectors)

def dictfetchall(cursor):
    "Return all rows from a cursor as a dict"
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]

def get_games_user_based_suggestions(user_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM games " +
                       "WHERE Game_ID in (SELECT Game_ID From Relation Where User_ID =" + str(user_id) + ");")
        data = dictfetchall(cursor)
        cursor.close()
        return data

def get_game_sql(game_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM games WHERE Name NOT NULL AND Game_ID=" + str(game_id) + ";")
        game_rows = dictfetchall(cursor)	#[{'Game_ID': 1, 'Description': "...", Image:"...", ...}, {'Game_ID': 2, 'Description': "...", Image:"..."}...]
        print ("game_rows " + str(game_rows))
        cursor.close()
    return game_rows[0]

def user_based_recommendations(request):
    # create_table_game_category_vector()
    user_category_data, user_ids = np.split(get_all_users_category_vectors(), [-1], axis=1)
    user_ids = [j for i in user_ids for j in i]
    print ("user_category_data " + str(user_category_data))
    print ("user_ids " + str(user_ids))
    user_data_nn = NearestNeighbors(n_neighbors=2)
    user_data_nn.fit(user_category_data)
    recommended_user_ids = [j for i in user_data_nn.kneighbors([get_user_category_vector(request.user.id)], return_distance=False) for j in i]
    similar_users_id = []
    for user_id in recommended_user_ids:
        similar_users_id.append(user_ids[user_id])
    print ("similar user id " + str(similar_users_id))
    similar_user_suggestions = set()
    for user in similar_users_id:
        if user != request.user.id:
            # if not len(similar_user_suggestions):
            #     similar_user_suggestions = get_games_user_based_suggestions(user)
            # else:
            #     similar_user_suggestions = np.vstack([similar_user_suggestions, get_games_user_based_suggestions(user)])
            similar_user_suggestions.add(get_games_user_based_suggestions(user))
    return np.array(similar_user_suggestions)

def get_game_ids(user_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT Game_ID From Relation Where User_ID =" + str(user_id) + ";")
        game_ids = [e[0] for e in cursor.fetchall()]
        print (game_ids)
        cursor.close()
        return game_ids

def get_owned_games(user_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT Game_ID From Relation Where User_ID =" + str(user_id) + " AND Owned=1;")
        game_ids = [e[0] for e in cursor.fetchall()]
        print (game_ids)
        cursor.close()
        return game_ids

def game_based_recommandations(request):
    #create_table_game_category_vector() #Create Game_Category_Vectors that contains the item based game category vectors
    game_ids = get_game_ids(request.user.id)
    game_category_data = get_game_category_vectors()
    game_data_nn = NearestNeighbors(n_neighbors=5)
    game_data_nn.fit(game_category_data)
    similar_games_suggestions = []
    owned_games = get_owned_games(request.user.id)
    for game_id in game_ids:
        similar_games_id = game_data_nn.kneighbors([get_game_category_vector_recommendations(game_id)],
                                                   return_distance=False)
        print("similar_games_id" + str(similar_games_id[0]))
        for game in similar_games_id[0]:
            if game not in owned_games:
                similar_games_suggestions.append(get_game_sql(game))
    args = {"similar_games_suggestions": similar_games_suggestions}
    return render(request, "accounts/recommendations.html", args)
