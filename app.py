import os
import json
import base64
import psycopg2
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, render_template_string, redirect, url_for
import requests

app = Flask(__name__)

# Configuration
TMDB_API_KEY = "52f6a75a38a397d940959b336801e1c3"
ADMIN_USERNAME = "venura"
ADMIN_PASSWORD = "venura"

# Database connection
def get_db_connection():
    return psycopg2.connect(os.environ.get('DATABASE_URL'))

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
            id SERIAL PRIMARY KEY,
            type VARCHAR(10) NOT NULL CHECK (type IN ('movie','tv')),
            title TEXT NOT NULL,
            description TEXT,
            thumbnail TEXT,
            release_date DATE,
            language VARCHAR(10),
            rating NUMERIC(3,1),
            cast JSON,
            video_links JSON,
            download_links JSON,
            total_seasons INT,
            seasons JSON
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

# TMDB API functions
def fetch_movie_from_tmdb(tmdb_id):
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=credits"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def fetch_tv_from_tmdb(tmdb_id):
    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=credits,seasons"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def format_tmdb_cast(credits):
    cast = []
    for actor in credits.get('cast', [])[:10]:  # Limit to top 10
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
            'id': row[0],
            'type': row[1],
            'title': row[2],
            'description': row[3],
            'thumbnail': row[4],
            'release_date': row[5].isoformat() if row[5] else None,
            'language': row[6],
            'rating': float(row[7]) if row[7] else None,
            'cast': row[8],
            'video_links': row[9],
            'download_links': row[10]
        }
        
        if row[1] == 'tv':
            media['total_seasons'] = row[11]
            media['seasons'] = row[12]
            
        media_list.append(media)
    
    cur.close()
    conn.close()
    return jsonify(media_list)

@app.route('/api/media/<int:media_id>')
def api_get_media(media_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM media WHERE id = %s', (media_id,))
    row = cur.fetchone()
    
    if not row:
        return jsonify({'error': 'Media not found'}), 404
    
    media = {
        'id': row[0],
        'type': row[1],
        'title': row[2],
        'description': row[3],
        'thumbnail': row[4],
        'release_date': row[5].isoformat() if row[5] else None,
        'language': row[6],
        'rating': float(row[7]) if row[7] else None,
        'cast': row[8],
        'video_links': row[9],
        'download_links': row[10]
    }
    
    if row[1] == 'tv':
        media['total_seasons'] = row[11]
        media['seasons'] = row[12]
    
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
        body { font-family: Arial, sans-serif; margin: 40px; background: #0d1b2a; color: #fff; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #14a085; text-align: center; }
        .nav-links { display: flex; flex-wrap: wrap; gap: 15px; margin: 30px 0; }
        .nav-links a { 
            background: #14a085; color: white; padding: 12px 20px; 
            text-decoration: none; border-radius: 6px; font-weight: bold;
        }
        .nav-links a:hover { background: #0f7a66; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 Movie & TV Database Admin</h1>
        <div class="nav-links">
            <a href="/admin/add_movie">🎬 Add Movie</a>
            <a href="/admin/add_tv">📺 Add TV Show</a>
            <a href="/admin/search">🔍 Search Media</a>
            <a href="/api/media" target="_blank">📊 API Data</a>
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
        body { font-family: Arial, sans-serif; margin: 40px; background: #0d1b2a; color: #fff; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #14a085; }
        form { background: #1e3a52; padding: 30px; border-radius: 8px; }
        label { display: block; margin: 15px 0 5px; font-weight: bold; }
        input, textarea { width: 100%; padding: 10px; border: none; border-radius: 4px; margin-bottom: 15px; }
        textarea { height: 100px; resize: vertical; }
        .json-area { height: 120px; }
        button { background: #14a085; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px; }
        button:hover { background: #0f7a66; }
        .back-link { color: #14a085; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/admin" class="back-link">← Back to Dashboard</a>
        <h1>🎬 Add Movie</h1>
        <form id="movieForm">
            <label>TMDB ID:</label>
            <input type="number" id="tmdb_id" placeholder="e.g., 27205 (for Inception)">
            <button type="button" onclick="fetchFromTMDB()">Fetch from TMDB</button>
            
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
            
            <button type="submit">Save Movie</button>
        </form>
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
                    alert('Movie added successfully!');
                    window.location.href = '/admin';
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
        body { font-family: Arial, sans-serif; margin: 40px; background: #0d1b2a; color: #fff; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #14a085; }
        form { background: #1e3a52; padding: 30px; border-radius: 8px; }
        label { display: block; margin: 15px 0 5px; font-weight: bold; }
        input, textarea { width: 100%; padding: 10px; border: none; border-radius: 4px; margin-bottom: 15px; }
        textarea { height: 100px; resize: vertical; }
        .json-area { height: 120px; }
        button { background: #14a085; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px; }
        button:hover { background: #0f7a66; }
        .back-link { color: #14a085; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/admin" class="back-link">← Back to Dashboard</a>
        <h1>📺 Add TV Show</h1>
        <form id="tvForm">
            <label>TMDB ID:</label>
            <input type="number" id="tmdb_id" placeholder="e.g., 1396 (for Breaking Bad)">
            <button type="button" onclick="fetchFromTMDB()">Fetch from TMDB</button>
            
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
            
            <button type="submit">Save TV Show</button>
        </form>
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
                    alert('TV Show added successfully!');
                    window.location.href = '/admin';
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

@app.route('/admin/search')
@requires_auth
def admin_search():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Search Media</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #0d1b2a; color: #fff; }
        .container { max-width: 1000px; margin: 0 auto; }
        h1 { color: #14a085; }
        .search-box { background: #1e3a52; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        input { padding: 10px; border: none; border-radius: 4px; margin-right: 10px; width: 300px; }
        button { background: #14a085; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0f7a66; }
        table { width: 100%; border-collapse: collapse; background: #1e3a52; border-radius: 8px; overflow: hidden; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #2a4a62; }
        th { background: #14a085; }
        .btn-small { padding: 6px 12px; font-size: 12px; margin-right: 5px; }
        .btn-danger { background: #dc3545; }
        .btn-danger:hover { background: #c82333; }
        .back-link { color: #14a085; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/admin" class="back-link">← Back to Dashboard</a>
        <h1>🔍 Search Media</h1>
        
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="Search by title or ID">
            <button onclick="searchMedia()">Search</button>
            <button onclick="loadAllMedia()">Show All</button>
        </div>
        
        <div id="resultsContainer">
            <table id="resultsTable" style="display: none;">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Type</th>
                        <th>Title</th>
                        <th>Release Date</th>
                        <th>Rating</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody id="resultsBody"></tbody>
            </table>
        </div>
    </div>
    
    <script>
        async function searchMedia() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) return loadAllMedia();
            
            try {
                const response = await fetch('/api/media');
                const data = await response.json();
                
                const filtered = data.filter(item => 
                    item.title.toLowerCase().includes(query.toLowerCase()) ||
                    item.id.toString() === query
                );
                
                displayResults(filtered);
            } catch (error) {
                alert('Error searching: ' + error.message);
            }
        }
        
        async function loadAllMedia() {
            try {
                const response = await fetch('/api/media');
                const data = await response.json();
                displayResults(data);
            } catch (error) {
                alert('Error loading media: ' + error.message);
            }
        }
        
        function displayResults(data) {
            const table = document.getElementById('resultsTable');
            const tbody = document.getElementById('resultsBody');
            
            tbody.innerHTML = '';
            
            if (data.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6">No results found</td></tr>';
            } else {
                data.forEach(item => {
                    const row = tbody.insertRow();
                    row.innerHTML = `
                        <td>${item.id}</td>
                        <td>${item.type.toUpperCase()}</td>
                        <td>${item.title}</td>
                        <td>${item.release_date || 'N/A'}</td>
                        <td>${item.rating || 'N/A'}</td>
                        <td>
                            <button class="btn-small" onclick="editMedia(${item.id})">Edit</button>
                            <button class="btn-small btn-danger" onclick="deleteMedia(${item.id}, '${item.title}')">Delete</button>
                            ${item.type === 'tv' ? `<button class="btn-small" onclick="addEpisode(${item.id})">Add Episode</button>` : ''}
                        </td>
                    `;
                });
            }
            
            table.style.display = 'table';
        }
        
        function editMedia(id) {
            window.location.href = `/admin/edit/${id}`;
        }
        
        async function deleteMedia(id, title) {
            if (!confirm(`Are you sure you want to delete "${title}"?`)) return;
            
            try {
                const response = await fetch(`/admin/media/${id}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    alert('Media deleted successfully!');
                    loadAllMedia();
                } else {
                    alert('Error deleting media');
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }
        
        function addEpisode(id) {
            window.location.href = `/admin/add_episode/${id}`;
        }
        
        // Load all media on page load
        loadAllMedia();
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (
            data['type'], data['title'], data['description'], data['thumbnail'],
            data['release_date'] or None, data['language'], data['rating'],
            json.dumps(data['cast']), data.get('total_seasons'),
            json.dumps(data.get('seasons', {}))
        ))
    
    media_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'id': media_id, 'message': 'Media created successfully'})

@app.route('/admin/media/<int:media_id>', methods=['DELETE'])
@requires_auth
def delete_media(media_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM media WHERE id = %s', (media_id,))
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'message': 'Media deleted successfully'})

# Initialize database on startup
try:
    init_db()
except:
    pass  # Database might already exist

# Vercel serverless function handler
def handler(request):
    return app(request.environ, lambda *args: None)

if __name__ == '__main__':
    app.run(debug=True)
