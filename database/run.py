from app import create_app

app = create_app()

if __name__ == '__main__':
    socketio = app.config.get('socketio_instance')
    if socketio:
        # allow_unsafe_werkzeug is fine for local dev
        socketio.run(app, debug=True, port=5001, allow_unsafe_werkzeug=True)
    else:
        app.run(debug=True, port=5001)