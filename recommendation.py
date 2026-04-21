{% extends 'layout.html' %}
{% block title %}Admin Login{% endblock %}

{% block content %}
<div class="form-card">
    <h2>Admin Login</h2>
    <form method="POST">
        <input type="text" name="username" placeholder="Enter username" required>
        <input type="password" name="password" placeholder="Enter password" required>
        <button type="submit" class="btn">Login</button>
    </form>
</div>
{% endblock %}
