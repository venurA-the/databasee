# Add these routes to your main app.py file

@app.route('/admin/edit/<int:media_id>')
@requires_auth
def admin_edit_media(media_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM media WHERE id = %s', (media_id,))
    media = cur.fetchone()
    cur.close()
    conn.close()
    
    if not media:
        return "Media not found", 404
    
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Edit Media</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #0d1b2a; color: #fff; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #14a085; }
        form { background: #1e3a52; padding: 30px; border-radius: 8px; }
        label { display: block; margin: 15px 0 5px; font-weight: bold; }
        input, textarea { width: 100%; padding: 10px; border: none; border-radius: 4px; margin-bottom: 15px; }
        textarea { height: 100px; resize: vertical; }
        .json-area { height: 120px; }
        button { background: #14a085; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0f7a66; }
        .back-link { color: #14a085; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/admin/search" class="back-link">← Back to Search</a>
        <h1>✏️ Edit: {{ title }}</h1>
        <form id="editForm">
            <input type="hidden" id="media_id" value="{{ media_id }}">
            <input type="hidden" id="media_type" value="{{ media_type }}">
            
            <label>Title:</label>
            <input type="text" id="title" value="{{ title }}" required>
            
            <label>Description:</label>
            <textarea id="description">{{ description }}</textarea>
            
            <label>Thumbnail URL:</label>
            <input type="url" id="thumbnail" value="{{ thumbnail }}">
            
            <label>Release Date:</label>
            <input type="date" id="release_date" value="{{ release_date }}">
            
            <label>Language:</label>
            <input type="text" id="language" value="{{ language }}">
            
            <label>Rating:</label>
            <input type="number" id="rating" step="0.1" min="0" max="10" value="{{ rating }}">
            
            {% if media_type == 'tv' %}
            <label>Total Seasons:</label>
            <input type="number" id="total_seasons" value="{{ total_seasons }}">
            {% endif %}
            
            <label>Cast (JSON):</label>
            <textarea id="cast" class="json-area">{{ cast_json }}</textarea>
            
            {% if media_type == 'movie' %}
            <label>Video Links (JSON):</label>
            <textarea id="video_links" class="json-area">{{ video_links_json }}</textarea>
            
            <label>Download Links (JSON):</label>
            <textarea id="download_links" class="json-area">{{ download_links_json }}</textarea>
            {% endif %}
            
            {% if media_type == 'tv' %}
            <label>Seasons (JSON):</label>
            <textarea id="seasons" class="json-area">{{ seasons_json }}</textarea>
            {% endif %}
            
            <button type="submit">Update Media</button>
        </form>
    </div>
    
    <script>
        document.getElementById('editForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const mediaType = document.getElementById('media_type').value;
            const mediaId = document.getElementById('media_id').value;
            
            const formData = {
                type: mediaType,
                title: document.getElementById('title').value,
                description: document.getElementById('description').value,
                thumbnail: document.getElementById('thumbnail').value,
                release_date: document.getElementById('release_date').value,
                language: document.getElementById('language').value,
                rating: parseFloat(document.getElementById('rating').value) || null,
                cast: JSON.parse(document.getElementById('cast').value || '[]')
            };
            
            if (mediaType === 'movie') {
                formData.video_links = JSON.parse(document.getElementById('video_links').value || '{}');
                formData.download_links = JSON.parse(document.getElementById('download_links').value || '{}');
            } else {
                formData.total_seasons = parseInt(document.getElementById('total_seasons').value) || null;
                formData.seasons = JSON.parse(document.getElementById('seasons').value || '{}');
            }
            
            try {
                const response = await fetch(`/admin/media/${mediaId}`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(formData)
                });
                
                if (response.ok) {
                    alert('Media updated successfully!');
                    window.location.href = '/admin/search';
                } else {
                    alert('Error updating media');
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        });
    </script>
</body>
</html>
    ''', media_id=media[0], media_type=media[1], title=media[2], 
         description=media[3] or '', thumbnail=media[4] or '', 
         release_date=media[5].isoformat() if media[5] else '',
         language=media[6] or '', rating=float(media[7]) if media[7] else '',
         cast_json=json.dumps(media[8], indent=2) if media[8] else '[]',
         video_links_json=json.dumps(media[9], indent=2) if media[9] else '{}',
         download_links_json=json.dumps(media[10], indent=2) if media[10] else '{}',
         total_seasons=media[11] if media[1] == 'tv' else '',
         seasons_json=json.dumps(media[12], indent=2) if media[1] == 'tv' and media[12] else '{}')

@app.route('/admin/media/<int:media_id>', methods=['PUT'])
@requires_auth
def update_media(media_id):
    data = request.get_json()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    if data['type'] == 'movie':
        cur.execute('''
            UPDATE media SET title=%s, description=%s, thumbnail=%s, release_date=%s,
                           language=%s, rating=%s, cast=%s, video_links=%s, download_links=%s
            WHERE id=%s
        ''', (
            data['title'], data['description'], data['thumbnail'],
            data['release_date'] or None, data['language'], data['rating'],
            json.dumps(data['cast']), json.dumps(data['video_links']),
            json.dumps(data['download_links']), media_id
        ))
    else:  # TV show
        cur.execute('''
            UPDATE media SET title=%s, description=%s, thumbnail=%s, release_date=%s,
                           language=%s, rating=%s, cast=%s, total_seasons=%s, seasons=%s
            WHERE id=%s
        ''', (
            data['title'], data['description'], data['thumbnail'],
            data['release_date'] or None, data['language'], data['rating'],
            json.dumps(data['cast']), data.get('total_seasons'),
            json.dumps(data.get('seasons', {})), media_id
        ))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'message': 'Media updated successfully'})

@app.route('/admin/add_episode/<int:media_id>')
@requires_auth
def admin_add_episode(media_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT title, seasons FROM media WHERE id = %s AND type = %s', (media_id, 'tv'))
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    if not result:
        return "TV show not found", 404
    
    title, seasons = result
    seasons = seasons or {}
    
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Add Episode to {{ title }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #0d1b2a; color: #fff; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #14a085; }
        form { background: #1e3a52; padding: 30px; border-radius: 8px; }
        label { display: block; margin: 15px 0 5px; font-weight: bold; }
        input, textarea { width: 100%; padding: 10px; border: none; border-radius: 4px; margin-bottom: 15px; }
        textarea { height: 120px; resize: vertical; }
        button { background: #14a085; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0f7a66; }
        .back-link { color: #14a085; text-decoration: none; }
        .current-seasons { background: #2a4a62; padding: 15px; border-radius: 4px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/admin/search" class="back-link">← Back to Search</a>
        <h1>🎞 Add Episode to "{{ title }}"</h1>
        
        {% if seasons %}
        <div class="current-seasons">
            <strong>Current Seasons:</strong>
            {% for season_key in seasons %}
                Season {{ seasons[season_key].season_number }} ({{ seasons[season_key].total_episodes }} episodes) |
            {% endfor %}
        </div>
        {% endif %}
        
        <form id="episodeForm">
            <input type="hidden" id="media_id" value="{{ media_id }}">
            
            <label>Season Number:</label>
            <input type="number" id="season_number" min="1" required>
            
            <label>Episode Number:</label>
            <input type="number" id="episode_number" min="1" required>
            
            <label>Episode Name:</label>
            <input type="text" id="episode_name" required>
            
            <label>Video Links (JSON):</label>
            <textarea id="video_links" placeholder='{"video_720p": "url", "video_1080p": "url", "video_2160p": "url"}'></textarea>
            
            <label>Download Links (JSON):</label>
            <textarea id="download_links" placeholder='{"download_720p": {"url": "url", "file_type": "webrip"}}'></textarea>
            
            <button type="submit">Save Episode</button>
        </form>
    </div>
    
    <script>
        document.getElementById('episodeForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const mediaId = document.getElementById('media_id').value;
            const seasonNumber = parseInt(document.getElementById('season_number').value);
            const episodeNumber = parseInt(document.getElementById('episode_number').value);
            
            const episodeData = {
                season_number: seasonNumber,
                episode_number: episodeNumber,
                episode_name: document.getElementById('episode_name').value,
                video_links: JSON.parse(document.getElementById('video_links').value || '{}'),
                download_links: JSON.parse(document.getElementById('download_links').value || '{}')
            };
            
            try {
                const response = await fetch(`/admin/episode/${mediaId}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(episodeData)
                });
                
                if (response.ok) {
                    alert('Episode added successfully!');
                    document.getElementById('episodeForm').reset();
                } else {
                    alert('Error adding episode');
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        });
    </script>
</body>
</html>
    ''', title=title, media_id=media_id, seasons=seasons)

@app.route('/admin/episode/<int:media_id>', methods=['POST'])
@requires_auth
def add_episode(media_id):
    data = request.get_json()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get current seasons data
    cur.execute('SELECT seasons FROM media WHERE id = %s AND type = %s', (media_id, 'tv'))
    result = cur.fetchone()
    
    if not result:
        return jsonify({'error': 'TV show not found'}), 404
    
    seasons = result[0] or {}
    season_key = f"season_{data['season_number']}"
    
    # Initialize season if it doesn't exist
    if season_key not in seasons:
        seasons[season_key] = {
            'season_number': data['season_number'],
            'total_episodes': 0,
            'episodes': []
        }
    
    # Create episode object
    episode = {
        'episode_number': data['episode_number'],
        'episode_name': data['episode_name']
    }
    
    # Add video links directly to episode
    video_links = data.get('video_links', {})
    for quality, url in video_links.items():
        episode[quality] = url
    
    # Add download links directly to episode
    download_links = data.get('download_links', {})
    for quality, link_data in download_links.items():
        episode[quality] = link_data
    
    # Add episode to season
    seasons[season_key]['episodes'].append(episode)
    seasons[season_key]['total_episodes'] = len(seasons[season_key]['episodes'])
    
    # Update database
    cur.execute('UPDATE media SET seasons = %s WHERE id = %s', (json.dumps(seasons), media_id))
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({'message': 'Episode added successfully'})
