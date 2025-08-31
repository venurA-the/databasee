import os
import json
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, render_template_string
import requests

app = Flask(__name__)

# Configuration
TMDB_API_KEY = "52f6a75a38a397d940959b336801e1c3"
ADMIN_USERNAME = "venura"
ADMIN_PASSWORD = "venura"

# Database file location (temporary for Vercel)
DB_FILE = '/tmp/media.db' if os.environ.get('VERCEL') else 'media.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Basic Auth decorator
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != ADMIN_USERNAME or auth.password != ADMIN_PASSWORD:
            return ('Unauthorized', 401, {
                'WWW-Authenticate': 'Basic realm="Admin Panel"'
            })
        return f(*args, **kwargs)
    return decorated

# Database initialization
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL CHECK (type IN ('movie','tv')),
            title TEXT NOT NULL,
            description TEXT,
            thumbnail TEXT,
            release_date DATE,
            language TEXT,
            rating REAL,
            cast TEXT,
            video_links TEXT,
            download_links TEXT,
            total_seasons INTEGER,
            seasons TEXT
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

# TMDB API functions
def fetch_movie_from_tmdb(tmdb_id):
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=credits"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def fetch_tv_from_tmdb(tmdb_id):
    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=credits,seasons"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def format_tmdb_cast(credits):
    cast = []
    for actor in credits.get('cast', [])[:10]:
        cast.append({
            'name': actor.get('name'),
            'character': actor.get('character'),
            'image': f"https://image.tmdb.org/t/p/original{actor.get('profile_path')}" if actor.get('profile_path') else None
        })
    return cast

# API Routes
@app.route('/api/media')
def api_get_all_media():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM media ORDER BY id DESC')
    media_list = []
    
    for row in cur.fetchall():
        media = {
            'id': row['id'],
            'type': row['type'],
            'title': row['title'],
            'description': row['description'],
            'thumbnail': row['thumbnail'],
            'release_date': row['release_date'],
            'language': row['language'],
            'rating': row['rating'],
            'cast': json.loads(row['cast']) if row['cast'] else [],
            'video_links': json.loads(row['video_links']) if row['video_links'] else {},
            'download_links': json.loads(row['download_links']) if row['download_links'] else {}
        }
        
        if row['type'] == 'tv':
            media['total_seasons'] = row['total_seasons']
            media['seasons'] = json.loads(row['seasons']) if row['seasons'] else {}
            
        media_list.append(media)
    
    cur.close()
    conn.close()
    return jsonify(media_list)

@app.route('/api/media/<int:media_id>')
def api_get_media(media_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM media WHERE id = ?', (media_id,))
    row = cur.fetchone()
    
    if not row:
        return jsonify({'error': 'Media not found'}), 404
    
    media = {
        'id': row['id'],
        'type': row['type'],
        'title': row['title'],
        'description': row['description'],
        'thumbnail': row['thumbnail'],
        'release_date': row['release_date'],
        'language': row['language'],
        'rating': row['rating'],
        'cast': json.loads(row['cast']) if row['cast'] else [],
        'video_links': json.loads(row['video_links']) if row['video_links'] else {},
        'download_links': json.loads(row['download_links']) if row['download_links'] else {}
    }
    
    if row['type'] == 'tv':
        media['total_seasons'] = row['total_seasons']
        media['seasons'] = json.loads(row['seasons']) if row['seasons'] else {}
    
    cur.close()
    conn.close()
    return jsonify(media)

# Admin Routes
@app.route('/admin')
@requires_auth
def admin_dashboard():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Movie & TV Database Admin</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 40px; background: linear-gradient(135deg, #0d1b2a 0%, #1e3a52 100%); color: #fff; min-height: 100vh; }
        .container { max-width: 900px; margin: 0 auto; }
        h1 { color: #14a085; text-align: center; font-size: 2.5em; margin-bottom: 10px; }
        .subtitle { text-align: center; color: #8fb8c4; margin-bottom: 40px; font-size: 1.1em; }
        .nav-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 40px 0; }
        .nav-card { 
            background: linear-gradient(145deg, #1e3a52, #2a4a62); 
            padding: 25px; border-radius: 12px; text-decoration: none; color: white; 
            transition: all 0.3s ease; border: 2px solid transparent;
            text-align: center;
        }
        .nav-card:hover { 
            transform: translateY(-5px); border-color: #14a085; 
            box-shadow: 0 10px 30px rgba(20, 160, 133, 0.3);
        }
        .nav-card h3 { margin: 0 0 10px; color: #14a085; font-size: 1.3em; }
        .nav-card p { margin: 0; color: #b0c4de; font-size: 0.9em; }
        .footer { text-align: center; margin-top: 60px; color: #8fb8c4; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 Movie & TV Database</h1>
        <p class="subtitle">Professional Media Management System</p>
        
        <div class="nav-grid">
            <a href="/admin/add_movie" class="nav-card">
                <h3>🎬 Add Movie</h3>
                <p>Add new movies with TMDB integration</p>
            </a>
            <a href="/admin/add_tv" class="nav-card">
                <h3>📺 Add TV Show</h3>
                <p>Add TV series and manage seasons</p>
            </a>
            <a href="/admin/search" class="nav-card">
                <h3>🔍 Manage Media</h3>
                <p>Search, edit, and delete content</p>
            </a>
            <a href="/api/media" target="_blank" class="nav-card">
                <h3>📊 View API</h3>
                <p>Browse JSON API data</p>
            </a>
        </div>
        
        <div class="footer">
            <p>Powered by TMDB API • Deployed on Vercel</p>
        </div>
    </div>
</body>
</html>
    ''')

@app.route('/admin/add_movie')
@requires_auth
def admin_add_movie():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Add Movie</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 40px; background: linear-gradient(135deg, #0d1b2a 0%, #1e3a52 100%); color: #fff; min-height: 100vh; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #14a085; margin-bottom: 30px; }
        .form-container { background: rgba(30, 58, 82, 0.8); padding: 40px; border-radius: 12px; backdrop-filter: blur(10px); }
        label { display: block; margin: 20px 0 8px; font-weight: 600; color: #b0c4de; }
        input, textarea { width: 100%; padding: 12px; border: 2px solid #2a4a62; border-radius: 6px; background: #1e3a52; color: #fff; font-size: 14px; }
        input:focus, textarea:focus { outline: none; border-color: #14a085; }
        textarea { height: 100px; resize: vertical; font-family: inherit; }
        .json-area { height: 120px; font-family: 'Courier New', monospace; }
        .btn { background: linear-gradient(45deg, #14a085, #0f7a66); color: white; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; margin-right: 10px; transition: all 0.3s; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(20, 160, 133, 0.4); }
        .back-link { color: #14a085; text-decoration: none; font-weight: 600; }
        .back-link:hover { text-decoration: underline; }
        .success { background: #27ae60; color: white; padding: 10px; border-radius: 6px; margin: 10px 0; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/admin" class="back-link">← Back to Dashboard</a>
        <h1>🎬 Add Movie</h1>
        <div class="form-container">
            <div id="successMsg" class="success">Movie added successfully!</div>
            <form id="movieForm">
                <label>TMDB ID:</label>
                <input type="number" id="tmdb_id" placeholder="e.g., 27205 (for Inception)">
                <button type="button" class="btn" onclick="fetchFromTMDB()">Fetch from TMDB</button>
                
                <label>Title:</label>
                <input type="text" id="title" required>
                
                <label>Description:</label>
                <textarea id="description"></textarea>
                
                <label>Thumbnail URL:</label>
                <input type="url" id="thumbnail">
                
                <label>Release Date:</label>
                <input type="date" id="release_date">
                
                <label>Language:</label>
                <input type="text" id="language" placeholder="e.g., en">
                
                <label>Rating:</label>
                <input type="number" id="rating" step="0.1" min="0" max="10">
                
                <label>Cast (JSON):</label>
                <textarea id="cast" class="json-area" placeholder='[{"name": "Actor Name", "character": "Character", "image": "url"}]'></textarea>
                
                <label>Video Links (JSON):</label>
                <textarea id="video_links" class="json-area" placeholder='{"video_720p": "url", "video_1080p": "url", "video_2160p": "url"}'></textarea>
                
                <label>Download Links (JSON):</label>
                <textarea id="download_links" class="json-area" placeholder='{"download_720p": {"url": "url", "file_type": "webrip"}}'></textarea>
                
                <button type="submit" class="btn">Save Movie</button>
            </form>
        </div>
    </div>
    
    <script>
        async function fetchFromTMDB() {
            const tmdbId = document.getElementById('tmdb_id').value;
            if (!tmdbId) return alert('Please enter TMDB ID');
            
            try {
                const response = await fetch('/admin/fetch_tmdb_movie/' + tmdbId);
                const data = await response.json();
                
                if (data.error) {
                    alert(data.error);
                    return;
                }
                
                document.getElementById('title').value = data.title || '';
                document.getElementById('description').value = data.overview || '';
                document.getElementById('thumbnail').value = data.poster_path ? `https://image.tmdb.org/t/p/original${data.poster_path}` : '';
                document.getElementById('release_date').value = data.release_date || '';
                document.getElementById('language').value = data.original_language || '';
                document.getElementById('rating').value = data.vote_average || '';
                document.getElementById('cast').value = JSON.stringify(data.cast, null, 2);
                
            } catch (error) {
                alert('Error fetching from TMDB: ' + error.message);
            }
        }
        
        document.getElementById('movieForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = {
                type: 'movie',
                title: document.getElementById('title').value,
                description: document.getElementById('description').value,
                thumbnail: document.getElementById('thumbnail').value,
                release_date: document.getElementById('release_date').value,
                language: document.getElementById('language').value,
                rating: parseFloat(document.getElementById('rating').value) || null,
                cast: JSON.parse(document.getElementById('cast').value || '[]'),
                video_links: JSON.parse(document.getElementById('video_links').value || '{}'),
                download_links: JSON.parse(document.getElementById('download_links').value || '{}')
            };
            
            try {
                const response = await fetch('/admin/media', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(formData)
                });
                
                if (response.ok) {
                    document.getElementById('successMsg').style.display = 'block';
                    document.getElementById('movieForm').reset();
                    setTimeout(() => {
                        document.getElementById('successMsg').style.display = 'none';
                    }, 3000);
                } else {
                    alert('Error adding movie');
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        });
    </script>
</body>
</html>
    ''')

@app.route('/admin/add_tv')
@requires_auth  
def admin_add_tv():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Add TV Show</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 40px; background: linear-gradient(135deg, #0d1b2a 0%, #1e3a52 100%); color: #fff; min-height: 100vh; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #14a085; margin-bottom: 30px; }
        .form-container { background: rgba(30, 58, 82, 0.8); padding: 40px; border-radius: 12px; backdrop-filter: blur(10px); }
        label { display: block; margin: 20px 0 8px; font-weight: 600; color: #b0c4de; }
        input, textarea { width: 100%; padding: 12px; border: 2px solid #2a4a62; border-radius: 6px; background: #1e3a52; color: #fff; font-size: 14px; }
        input:focus, textarea:focus { outline: none; border-color: #14a085; }
        textarea { height: 100px; resize: vertical; font-family: inherit; }
        .json-area { height: 120px; font-family: 'Courier New', monospace; }
        .btn { background: linear-gradient(45deg, #14a085, #0f7a66); color: white; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; margin-right: 10px; transition: all 0.3s; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(20, 160, 133, 0.4); }
        .back-link { color: #14a085; text-decoration: none; font-weight: 600; }
        .back-link:hover { text-decoration: underline; }
        .success { background: #27ae60; color: white; padding: 10px; border-radius: 6px; margin: 10px 0; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/admin" class="back-link">← Back to Dashboard</a>
        <h1>📺 Add TV Show</h1>
        <div class="form-container">
            <div id="successMsg" class="success">TV Show added successfully!</div>
            <form id="tvForm">
                <label>TMDB ID:</label>
                <input type="number" id="tmdb_id" placeholder="e.g., 1396 (for Breaking Bad)">
                <button type="button" class="btn" onclick="fetchFromTMDB()">Fetch from TMDB</button>
                
                <label>Title:</label>
                <input type="text" id="title" required>
                
                <label>Description:</label>
                <textarea id="description"></textarea>
                
                <label>Thumbnail URL:</label>
                <input type="url" id="thumbnail">
                
                <label>Release Date:</label>
                <input type="date" id="release_date">
                
                <label>Language:</label>
                <input type="text" id="language" placeholder="e.g., en">
                
                <label>Rating:</label>
                <input type="number" id="rating" step="0.1" min="0" max="10">
                
                <label>Total Seasons:</label>
                <input type="number" id="total_seasons">
                
                <label>Cast (JSON):</label>
                <textarea id="cast" class="json-area" placeholder='[{"name": "Actor Name", "character": "Character", "image": "url"}]'></textarea>
                
                <button type="submit" class="btn">Save TV Show</button>
            </form>
        </div>
    </div>
    
    <script>
        async function fetchFromTMDB() {
            const tmdbId = document.getElementById('tmdb_id').value;
            if (!tmdbId) return alert('Please enter TMDB ID');
            
            try {
                const response = await fetch('/admin/fetch_tmdb_tv/' + tmdbId);
                const data = await response.json();
                
                if (data.error) {
                    alert(data.error);
                    return;
                }
                
                document.getElementById('title').value = data.name || '';
                document.getElementById('description').value = data.overview || '';
                document.getElementById('thumbnail').value = data.poster_path ? `https://image.tmdb.org/t/p/original${data.poster_path}` : '';
                document.getElementById('release_date').value = data.first_air_date || '';
                document.getElementById('language').value = data.original_language || '';
                document.getElementById('rating').value = data.vote_average || '';
                document.getElementById('total_seasons').value = data.number_of_seasons || '';
                document.getElementById('cast').value = JSON.stringify(data.cast, null, 2);
                
            } catch (error) {
                alert('Error fetching from TMDB: ' + error.message);
            }
        }
        
        document.getElementById('tvForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = {
                type: 'tv',
                title: document.getElementById('title').value,
                description: document.getElementById('description').value,
                thumbnail: document.getElementById('thumbnail').value,
                release_date: document.getElementById('release_date').value,
                language: document.getElementById('language').value,
                rating: parseFloat(document.getElementById('rating').value) || null,
                total_seasons: parseInt(document.getElementById('total_seasons').value) || null,
                cast: JSON.parse(document.getElementById('cast').value || '[]'),
                seasons: {}
            };
            
            try {
                const response = await fetch('/admin/media', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(formData)
                });
                
                if (response.ok) {
                    document.getElementById('successMsg').style.display = 'block';
                    document.getElementById('tvForm').reset();
                    setTimeout(() => {
                        document.getElementById('successMsg').style.display = 'none';
                    }, 3000);
                } else {
                    alert('Error adding TV show');
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        });
    </script>
</body>
</html>
    ''')

# TMDB fetch endpoints
@app.route('/admin/fetch_tmdb_movie/<int:tmdb_id>')
@requires_auth
def fetch_tmdb_movie(tmdb_id):
    data = fetch_movie_from_tmdb(tmdb_id)
    if data:
        data['cast'] = format_tmdb_cast(data.get('credits', {}))
        return jsonify(data)
    return jsonify({'error': 'Movie not found'}), 404

@app.route('/admin/fetch_tmdb_tv/<int:tmdb_id>')
@requires_auth
def fetch_tmdb_tv(tmdb_id):
    data = fetch_tv_from_tmdb(tmdb_id)
    if data:
        data['cast'] = format_tmdb_cast(data.get('credits', {}))
        return jsonify(data)
    return jsonify({'error': 'TV show not found'}), 404

# Media CRUD operations
@app.route('/admin/media', methods=['POST'])
@requires_auth
def create_media():
    data = request.get_json()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if data['type'] == 'movie':
        cur.execute('''
            INSERT INTO media (type, title, description, thumbnail, release_date, 
                             language, rating, cast, video_links, download_links)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['type'], data['title'], data['description'], data['thumbnail'],
            data['release_date'] or None, data['language'], data['rating'],
            json.dumps(data['cast']), json.dumps(data['video_links']),
            json.dumps(data['download_links'])
        ))
    else:  # TV show
        cur.execute('''
            INSERT INTO media (type, title, description, thumbnail, release_date,
                             language, rating, cast, total_seasons, seasons)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['type'], data['title'], data['description'], data['thumbnail'],
            data['release_date'] or None, data['language'], data['rating'],
            json.dumps(data['cast']), data.get('total_seasons'),
            json.dumps(data.get('seasons', {}))
        ))
    
    media_id = cur.lastrowid
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'id': media_id, 'message': 'Media created successfully'})

@app.route('/admin/media/<int:media_id>', methods=['DELETE'])
@requires_auth
def delete_media(media_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM media WHERE id = ?', (media_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'message': 'Media deleted successfully'})

# Initialize database on startup
try:
    init_db()
except:
    pass

# Vercel handler
def handler(request):
    return app(request.environ, lambda *args: None)

if __name__ == '__main__':
    app.run(debug=True)
