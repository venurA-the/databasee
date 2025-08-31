import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, g
import psycopg2
import psycopg2.extras
from functools import wraps
import requests
import json
from werkzeug.security import generate_password_hash, check_password_hash
from base64 import b64decode

app = Flask(__name__)

# --- Configuration ---
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    # Use a dummy URL for local development
    DATABASE_URL = 'postgresql://user:password@localhost/dbname'

TMDB_API_KEY = "52f6a75a38a397d940959b336801e1c3"
ADMIN_USERNAME = "venura"
ADMIN_PASSWORD_HASH = generate_password_hash("venura")

# --- Database Connection ---
def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(DATABASE_URL, sslmode='require')
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- Basic Authentication ---
def check_auth(username, password):
    return username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password)

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'message': 'Authorization Required'}), 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}
        
        try:
            auth_type, credentials = auth_header.split()
            if auth_type.lower() == 'basic':
                decoded_credentials = b64decode(credentials).decode('utf-8')
                username, password = decoded_credentials.split(':', 1)
                if check_auth(username, password):
                    return f(*args, **kwargs)
        except Exception as e:
            print(f"Auth error: {e}")
        
        return jsonify({'message': 'Authorization Failed'}), 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}
    return decorated

# --- TMDB API Helper ---
def fetch_tmdb_data(tmdb_id, media_type):
    if media_type == 'movie':
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=credits"
    elif media_type == 'tv':
        url = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=credits,seasons"
    else:
        return None
    
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        
        cast = []
        for member in data['credits']['cast'][:5]:  # Get top 5 cast members
            cast.append({
                "name": member.get("name"),
                "character": member.get("character"),
                "image": f"https://image.tmdb.org/t/p/original{member.get('profile_path')}" if member.get('profile_path') else None
            })

        processed_data = {
            'title': data.get('title') if media_type == 'movie' else data.get('name'),
            'description': data.get('overview'),
            'thumbnail': f"https://image.tmdb.org/t/p/original{data.get('poster_path')}" if data.get('poster_path') else None,
            'release_date': data.get('release_date') if media_type == 'movie' else data.get('first_air_date'),
            'language': data.get('original_language'),
            'rating': data.get('vote_average'),
            'cast': cast
        }
        
        if media_type == 'tv':
            processed_data['total_seasons'] = data.get('number_of_seasons')
            
        return processed_data
    return None

# --- API Endpoints (Public) ---
@app.route("/api/media", methods=["GET"])
def get_all_media():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM media;")
    media = cur.fetchall()
    return jsonify([dict(row) for row in media])

@app.route("/api/media/<int:media_id>", methods=["GET"])
def get_single_media(media_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM media WHERE id = %s;", (media_id,))
    media = cur.fetchone()
    if media:
        return jsonify(dict(media))
    return jsonify({"message": "Media not found"}), 404

# --- Admin API Endpoints (Protected) ---
@app.route("/admin/media", methods=["POST"])
@requires_auth
def add_media():
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO media (type, title, description, thumbnail, release_date, language, rating, cast, video_links, download_links, total_seasons, seasons)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            data.get('type'), data.get('title'), data.get('description'), data.get('thumbnail'),
            data.get('release_date'), data.get('language'), data.get('rating'),
            json.dumps(data.get('cast')), json.dumps(data.get('video_links')), json.dumps(data.get('download_links')),
            data.get('total_seasons'), json.dumps(data.get('seasons'))
        ))
        media_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"message": "Media added successfully", "id": media_id}), 201
    except (psycopg2.DatabaseError, json.JSONDecodeError) as e:
        conn.rollback()
        return jsonify({"message": "Error adding media", "error": str(e)}), 400
    
@app.route("/admin/media/<int:media_id>", methods=["PUT"])
@requires_auth
def update_media(media_id):
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE media SET
                type = %s, title = %s, description = %s, thumbnail = %s, release_date = %s,
                language = %s, rating = %s, cast = %s, video_links = %s, download_links = %s,
                total_seasons = %s, seasons = %s
            WHERE id = %s;
        """, (
            data.get('type'), data.get('title'), data.get('description'), data.get('thumbnail'),
            data.get('release_date'), data.get('language'), data.get('rating'),
            json.dumps(data.get('cast')), json.dumps(data.get('video_links')), json.dumps(data.get('download_links')),
            data.get('total_seasons'), json.dumps(data.get('seasons')), media_id
        ))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"message": "Media not found"}), 404
        return jsonify({"message": "Media updated successfully"}), 200
    except (psycopg2.DatabaseError, json.JSONDecodeError) as e:
        conn.rollback()
        return jsonify({"message": "Error updating media", "error": str(e)}), 400

@app.route("/admin/media/<int:media_id>", methods=["DELETE"])
@requires_auth
def delete_media(media_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM media WHERE id = %s;", (media_id,))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"message": "Media not found"}), 404
        return jsonify({"message": "Media deleted successfully"}), 200
    except psycopg2.DatabaseError as e:
        conn.rollback()
        return jsonify({"message": "Error deleting media", "error": str(e)}), 400
    
# --- Admin Panel Routes (HTML/JS) ---
@app.route("/admin", methods=["GET"])
@requires_auth
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route("/admin/add_movie", methods=["GET"])
@requires_auth
def add_movie_page():
    return render_template("add_movie.html")

@app.route("/admin/add_tv", methods=["GET"])
@requires_auth
def add_tv_page():
    return render_template("add_tv.html")

@app.route("/admin/add_episode/<int:media_id>", methods=["GET"])
@requires_auth
def add_episode_page(media_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM media WHERE id = %s;", (media_id,))
    media = cur.fetchone()
    if not media or media['type'] != 'tv':
        return jsonify({"message": "Media not found or is not a TV show"}), 404
    return render_template("add_episode.html", media=media)

@app.route("/admin/search", methods=["GET"])
@requires_auth
def search_page():
    return render_template("search.html")

@app.route("/admin/edit/<int:media_id>", methods=["GET"])
@requires_auth
def edit_page(media_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM media WHERE id = %s;", (media_id,))
    media = cur.fetchone()
    if not media:
        return jsonify({"message": "Media not found"}), 404
    
    # Convert JSON data to strings for textarea display
    media_dict = dict(media)
    if media_dict.get('cast'):
        media_dict['cast'] = json.dumps(media_dict['cast'], indent=2)
    if media_dict.get('video_links'):
        media_dict['video_links'] = json.dumps(media_dict['video_links'], indent=2)
    if media_dict.get('download_links'):
        media_dict['download_links'] = json.dumps(media_dict['download_links'], indent=2)
    if media_dict.get('seasons'):
        media_dict['seasons'] = json.dumps(media_dict['seasons'], indent=2)
        
    return render_template("edit.html", media=media_dict)

# --- TMDB Fetch Endpoint ---
@app.route("/admin/tmdb_fetch", methods=["POST"])
@requires_auth
def tmdb_fetch():
    data = request.json
    tmdb_id = data.get("tmdb_id")
    media_type = data.get("media_type")
    
    if not tmdb_id or not media_type:
        return jsonify({"message": "TMDB ID and media type are required"}), 400
    
    tmdb_data = fetch_tmdb_data(tmdb_id, media_type)
    if tmdb_data:
        return jsonify(tmdb_data), 200
    
    return jsonify({"message": "Failed to fetch data from TMDB"}), 404
    
# --- Episode Update Endpoint ---
@app.route("/admin/update_episode/<int:media_id>", methods=["POST"])
@requires_auth
def update_episode(media_id):
    data = request.json
    season_number = data.get("season_number")
    episode_number = data.get("episode_number")
    episode_name = data.get("episode_name")
    video_links = data.get("video_links")
    download_links = data.get("download_links")

    if not all([season_number, episode_number, episode_name]):
        return jsonify({"message": "Season and episode details are required"}), 400

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT seasons FROM media WHERE id = %s AND type = 'tv';", (media_id,))
    media = cur.fetchone()
    
    if not media:
        return jsonify({"message": "TV show not found"}), 404

    seasons = media['seasons'] or {}
    season_key = f"season_{season_number}"
    
    if season_key not in seasons:
        seasons[season_key] = {
            "season_number": season_number,
            "total_episodes": 0,
            "episodes": []
        }
    
    # Check if episode already exists to update
    episode_found = False
    for episode in seasons[season_key]["episodes"]:
        if episode["episode_number"] == episode_number:
            episode.update({
                "episode_name": episode_name,
                "video_links": video_links,
                "download_links": download_links
            })
            episode_found = True
            break
            
    if not episode_found:
        new_episode = {
            "episode_number": episode_number,
            "episode_name": episode_name,
            "video_links": video_links,
            "download_links": download_links
        }
        seasons[season_key]["episodes"].append(new_episode)
        seasons[season_key]["total_episodes"] = len(seasons[season_key]["episodes"])

    try:
        cur.execute("UPDATE media SET seasons = %s WHERE id = %s;", (json.dumps(seasons), media_id))
        conn.commit()
        return jsonify({"message": "Episode updated successfully"}), 200
    except psycopg2.DatabaseError as e:
        conn.rollback()
        return jsonify({"message": "Error updating episode", "error": str(e)}), 400

if __name__ == "__main__":
    app.run(debug=True)
