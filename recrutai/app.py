import os
import sys
import csv
from io import StringIO
from flask import Flask, render_template_string, redirect, url_for, session, flash, request, jsonify, make_response
from supabase import create_client, Client
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

# ==========================================
# CONFIGURATION
# ==========================================
app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "recrutai_production_key_v1"
)

app.config.update(
    SESSION_COOKIE_NAME="recrutai_session",
    SESSION_COOKIE_SECURE=True,      # REQUIRED for HTTPS
    SESSION_COOKIE_SAMESITE="None",  # REQUIRED for OAuth
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=86400
)


# SUPABASE CREDENTIALS
SUPABASE_URL = "https://ayzlmwziqlbydpmrbcwy.supabase.co"
SUPABASE_KEY = "sb_publishable_hviR1AjVT2aEB8O8Kuqumg_iUcqaf8Y"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Supabase Init Error: {e}")

# ==========================================
# UI LAYOUTS
# ==========================================

LAYOUT_APP = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RecruitAI</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap'); body { font-family: 'Inter', sans-serif; }</style>
</head>
<body class="bg-gray-50 h-screen flex overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-64 bg-slate-900 text-white flex flex-col fixed h-full transition-all duration-300">
        <div class="p-6 text-2xl font-bold text-center border-b border-slate-700">
            <i class="fa-solid fa-robot text-blue-400 mr-2"></i>RecruitAI
        </div>
        <nav class="flex-1 overflow-y-auto py-4">
            <ul class="space-y-2 px-4">
                <li><a href="/dashboard" class="flex items-center p-3 rounded-lg hover:bg-slate-800 transition"><i class="fa-solid fa-chart-pie w-6"></i> Dashboard</a></li>
                <li><a href="/job_roles" class="flex items-center p-3 rounded-lg hover:bg-slate-800 transition"><i class="fa-solid fa-briefcase w-6"></i> Job Roles</a></li>
                <li><a href="/ai_screening" class="flex items-center p-3 rounded-lg hover:bg-slate-800 transition"><i class="fa-solid fa-microchip w-6"></i> AI Screening</a></li>
                <li><a href="/candidates" class="flex items-center p-3 rounded-lg hover:bg-slate-800 transition"><i class="fa-solid fa-users w-6"></i> Candidates</a></li>
                <li><a href="/ranking" class="flex items-center p-3 rounded-lg hover:bg-slate-800 transition"><i class="fa-solid fa-trophy w-6"></i> Ranking</a></li>
                <li><a href="/admin" class="flex items-center p-3 rounded-lg hover:bg-slate-800 transition"><i class="fa-solid fa-user-gear w-6"></i> Admin</a></li>
            </ul>
        </nav>
        <div class="p-4 border-t border-slate-700">
            <a href="/logout" class="flex items-center justify-center p-3 bg-red-600 rounded-lg hover:bg-red-700 transition font-semibold"><i class="fa-solid fa-sign-out-alt mr-2"></i> Logout</a>
        </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 ml-64 p-8 overflow-y-auto">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                <div class="mb-4 p-4 rounded-lg {{ 'bg-green-100 text-green-700' if category == 'success' else 'bg-red-100 text-red-700' }} shadow-sm">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <!-- DYNAMIC CONTENT -->
        [[CONTENT]]
    </main>
</body>
</html>
"""

LAYOUT_AUTH = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RecruitAI Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap'); body { font-family: 'Inter', sans-serif; }</style>
</head>
<body class="bg-gradient-to-br from-blue-900 to-slate-900 min-h-screen flex items-center justify-center">
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
        <div class="fixed top-4 right-4 z-50">
            {% for category, message in messages %}
            <div class="mb-2 p-4 rounded shadow-lg {{ 'bg-green-100 text-green-700' if category == 'success' else 'bg-red-100 text-red-700' }}">{{ message }}</div>
            {% endfor %}
        </div>
        {% endif %}
    {% endwith %}

    [[CONTENT]]
</body>
</html>
"""

# ==========================================
# 3. PAGE CONTENT BLOCKS
# ==========================================

CONTENT_LOGIN = """
<!-- 3D Background Layer -->
<div id="bg-3d" class="fixed inset-0 z-0" style="pointer-events: none;"></div>

<div class="relative z-10 bg-white p-8 rounded-2xl shadow-2xl w-full max-w-md">
    <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-slate-800 mb-2">RecruitAI <span class="text-xs bg-blue-100 text-blue-600 px-2 py-1 rounded">PRO</span></h1>
        <p class="text-gray-500">Intelligent Resume Screening</p>
    </div>

    <div class="space-y-6">
        <!-- Google Login -->
        <a href="/login/google" class="w-full border border-gray-300 py-3 rounded-lg flex items-center justify-center hover:bg-gray-50 transition cursor-pointer font-medium text-slate-700 shadow-sm hover:shadow">
            <img src="https://www.svgrepo.com/show/475656/google-color.svg" class="w-5 h-5 mr-3" alt="Google"> 
            Continue with Google
        </a>
        
        <div class="relative flex py-2 items-center">
            <div class="flex-grow border-t border-gray-300"></div>
            <span class="flex-shrink mx-4 text-gray-400 text-sm">Or with Email</span>
            <div class="flex-grow border-t border-gray-300"></div>
        </div>

        <form action="/login" method="POST" id="authForm" class="space-y-4">
            <div><label class="block text-sm font-medium text-gray-700">Email</label><input type="email" name="email" required class="mt-1 w-full p-3 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"></div>
            <div><label class="block text-sm font-medium text-gray-700">Password</label><input type="password" name="password" required class="mt-1 w-full p-3 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500"></div>
            <button type="submit" class="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 transition shadow-lg">Sign In</button>
        </form>

        <div class="text-center text-sm text-gray-600">
            Don't have an account? 
            <a href="#" onclick="document.getElementById('authForm').action='/signup'; document.querySelector('button[type=submit]').innerText='Sign Up'; this.innerText='Back to Login';" class="text-blue-600 font-semibold hover:underline">Sign Up</a>
        </div>
    </div>
</div>

<!-- AUTO-CATCH TOKENS IF REDIRECTED TO HOME -->
<script>
    const hash = window.location.hash.substring(1);
    const params = new URLSearchParams(hash);
    const accessToken = params.get('access_token');
    
    if (accessToken) {
        // Redirect to callback page to handle the token
        window.location.href = '/auth/callback#' + hash;
    }
</script>

<!-- THREE.JS ANIMATION -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js"></script>
<script>
    window.addEventListener('load', function() {
        const container = document.getElementById('bg-3d');
        if (!container) return;

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
        
        renderer.setSize(window.innerWidth, window.innerHeight);
        container.appendChild(renderer.domElement);

        // Particles
        const particlesGeometry = new THREE.BufferGeometry();
        const particlesCount = 1000;
        const posArray = new Float32Array(particlesCount * 3);

        for(let i = 0; i < particlesCount * 3; i++) {
            posArray[i] = (Math.random() - 0.5) * 15;
        }

        particlesGeometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
        const particlesMaterial = new THREE.PointsMaterial({
            size: 0.015,
            color: 0x93c5fd, // Light blue
            transparent: true,
            opacity: 0.8
        });

        const particlesMesh = new THREE.Points(particlesGeometry, particlesMaterial);
        scene.add(particlesMesh);

        camera.position.z = 3;

        // Mouse interaction
        let mouseX = 0;
        let mouseY = 0;
        let targetX = 0;
        let targetY = 0;

        const windowHalfX = window.innerWidth / 2;
        const windowHalfY = window.innerHeight / 2;

        document.addEventListener('mousemove', (event) => {
            mouseX = (event.clientX - windowHalfX);
            mouseY = (event.clientY - windowHalfY);
        });

        const clock = new THREE.Clock();

        function animate() {
            targetX = mouseX * 0.001;
            targetY = mouseY * 0.001;

            const elapsedTime = clock.getElapsedTime();

            particlesMesh.rotation.y = .2 * elapsedTime;
            particlesMesh.rotation.x += .05 * (targetY - particlesMesh.rotation.x);
            particlesMesh.rotation.y += .05 * (targetX - particlesMesh.rotation.y);

            renderer.render(scene, camera);
            requestAnimationFrame(animate);
        }

        animate();

        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
    });
</script>
"""

CONTENT_CALLBACK = """
<div class="text-center text-white max-w-2xl mx-auto p-4">
    <div id="loading">
        <svg class="animate-spin h-10 w-10 mb-4 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
        <h2 class="text-2xl font-bold">Verifying Identity...</h2>
        <p class="text-gray-400 mt-2">Connecting to Supabase...</p>
    </div>
    
    <div id="error" class="hidden bg-red-100 p-6 rounded text-red-800 w-full text-left">
        <h3 class="font-bold text-lg border-b border-red-200 pb-2 mb-2">Login Failed</h3>
        <p class="text-sm">We could not log you in:</p>
        <pre id="error-msg" class="mt-2 text-xs font-mono bg-red-50 p-2 rounded border border-red-200 overflow-x-auto"></pre>
        <div class="mt-4 flex gap-4">
            <a href="/" class="bg-red-600 text-white py-2 px-4 rounded font-bold hover:bg-red-700">Back to Login</a>
        </div>
    </div>
</div>

<script>
    const hash = window.location.hash.substring(1);
    const params = new URLSearchParams(hash);
    const accessToken = params.get('access_token');
    const refreshToken = params.get('refresh_token');
    const errorDesc = params.get('error_description');
    
    const errorBox = document.getElementById('error');
    const loadingBox = document.getElementById('loading');
    const errorMsg = document.getElementById('error-msg');

    function showError(msg) {
        loadingBox.classList.add('hidden');
        errorBox.classList.remove('hidden');
        errorMsg.innerText = msg;
    }

    if (errorDesc) {
        showError("Google Error: " + errorDesc);
    } else if (accessToken) {
        // Send to server using fetch
        fetch('/auth/confirm', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ access_token: accessToken, refresh_token: refreshToken })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                window.location.href = '/dashboard';
            } else {
                showError("Server Error: " + data.message);
            }
        })
        .catch(err => {
            showError("Network Error: " + err);
        });
    } else {
        // Fallback for visual confirmation if code handled server-side failed to redirect
        showError("No Access Token found in URL (Implicit Flow).\\n\\nIf you see ?code= in the URL, the server should have handled it.");
    }
</script>
"""

# LOGIN SUCCESS PAGE (The "Pause" Screen) - Updated for simpler flow
CONTENT_LOGIN_SUCCESS = """
<div class="bg-white p-8 rounded-xl shadow-2xl max-w-md text-center">
    <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <i class="fa-solid fa-check text-2xl text-green-600"></i>
    </div>
    <h2 class="text-2xl font-bold text-gray-800 mb-2">Login Successful</h2>
    <p class="text-gray-500 mb-6">Your session has been created securely.</p>
    <a href="/dashboard" class="block w-full bg-blue-600 text-white py-3 rounded-lg font-bold hover:bg-blue-700 transition">
        Go to Dashboard <i class="fa-solid fa-arrow-right ml-2"></i>
    </a>
</div>
"""

CONTENT_DASHBOARD = """
<div class="mb-8">
    <h2 class="text-3xl font-bold text-slate-800">Welcome back!</h2>
    <p class="text-slate-500">Here's what's happening with your recruitment pipeline.</p>
</div>

<!-- Stats Grid -->
<div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
    <!-- Total Candidates -->
    <div class="bg-white p-6 rounded-xl shadow-sm border border-blue-100 relative overflow-hidden group hover:shadow-md transition">
        <div class="absolute right-0 top-0 h-full w-1/4 bg-gradient-to-l from-blue-50 to-transparent opacity-50"></div>
        <div class="relative z-10">
            <div class="flex items-center justify-between mb-4">
                <div class="p-2 bg-blue-100 text-blue-600 rounded-lg"><i class="fa-solid fa-users"></i></div>
                <span class="text-xs font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded">Total</span>
            </div>
            <div class="text-3xl font-bold text-slate-800">{{ stats.cands }}</div>
            <div class="text-sm text-gray-500 mt-1">Candidates Processed</div>
        </div>
    </div>

    <!-- Active Jobs -->
    <div class="bg-white p-6 rounded-xl shadow-sm border border-purple-100 relative overflow-hidden group hover:shadow-md transition">
        <div class="absolute right-0 top-0 h-full w-1/4 bg-gradient-to-l from-purple-50 to-transparent opacity-50"></div>
        <div class="relative z-10">
            <div class="flex items-center justify-between mb-4">
                <div class="p-2 bg-purple-100 text-purple-600 rounded-lg"><i class="fa-solid fa-briefcase"></i></div>
                <span class="text-xs font-bold text-purple-600 bg-purple-50 px-2 py-1 rounded">Active</span>
            </div>
            <div class="text-3xl font-bold text-slate-800">{{ stats.jobs }}</div>
            <div class="text-sm text-gray-500 mt-1">Job Roles</div>
        </div>
    </div>

    <!-- Shortlisted -->
    <div class="bg-white p-6 rounded-xl shadow-sm border border-green-100 relative overflow-hidden group hover:shadow-md transition">
        <div class="absolute right-0 top-0 h-full w-1/4 bg-gradient-to-l from-green-50 to-transparent opacity-50"></div>
        <div class="relative z-10">
            <div class="flex items-center justify-between mb-4">
                <div class="p-2 bg-green-100 text-green-600 rounded-lg"><i class="fa-solid fa-check-circle"></i></div>
                <span class="text-xs font-bold text-green-600 bg-green-50 px-2 py-1 rounded">Top</span>
            </div>
            <div class="text-3xl font-bold text-slate-800">{{ stats.short }}</div>
            <div class="text-sm text-gray-500 mt-1">Shortlisted</div>
        </div>
    </div>

    <!-- Avg Score -->
    <div class="bg-white p-6 rounded-xl shadow-sm border border-orange-100 relative overflow-hidden group hover:shadow-md transition">
        <div class="absolute right-0 top-0 h-full w-1/4 bg-gradient-to-l from-orange-50 to-transparent opacity-50"></div>
        <div class="relative z-10">
            <div class="flex items-center justify-between mb-4">
                <div class="p-2 bg-orange-100 text-orange-600 rounded-lg"><i class="fa-solid fa-chart-line"></i></div>
                <span class="text-xs font-bold text-orange-600 bg-orange-50 px-2 py-1 rounded">Quality</span>
            </div>
            <div class="text-3xl font-bold text-slate-800">{{ stats.avg }}%</div>
            <div class="text-sm text-gray-500 mt-1">Avg Match Score</div>
        </div>
    </div>
</div>

<div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
    <!-- Quick Actions -->
    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <h3 class="font-bold text-slate-800 mb-4 flex items-center"><i class="fa-solid fa-bolt text-yellow-500 mr-2"></i> Quick Actions</h3>
        <div class="space-y-3">
            <a href="/ai_screening" class="block p-3 rounded-lg border border-gray-100 hover:border-blue-200 hover:bg-blue-50 transition flex items-center group">
                <div class="w-10 h-10 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mr-3 group-hover:bg-blue-600 group-hover:text-white transition">
                    <i class="fa-solid fa-cloud-arrow-up"></i>
                </div>
                <div>
                    <div class="font-semibold text-slate-700">Upload Resumes</div>
                    <div class="text-xs text-gray-500">Screen new candidates</div>
                </div>
            </a>
            <a href="/job_roles" class="block p-3 rounded-lg border border-gray-100 hover:border-purple-200 hover:bg-purple-50 transition flex items-center group">
                <div class="w-10 h-10 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center mr-3 group-hover:bg-purple-600 group-hover:text-white transition">
                    <i class="fa-solid fa-plus"></i>
                </div>
                <div>
                    <div class="font-semibold text-slate-700">Add Job Role</div>
                    <div class="text-xs text-gray-500">Create new position</div>
                </div>
            </a>
            <a href="/candidates" class="block p-3 rounded-lg border border-gray-100 hover:border-green-200 hover:bg-green-50 transition flex items-center group">
                <div class="w-10 h-10 rounded-full bg-green-100 text-green-600 flex items-center justify-center mr-3 group-hover:bg-green-600 group-hover:text-white transition">
                    <i class="fa-solid fa-list-check"></i>
                </div>
                <div>
                    <div class="font-semibold text-slate-700">Review Candidates</div>
                    <div class="text-xs text-gray-500">Check statuses</div>
                </div>
            </a>
        </div>
    </div>

    <!-- Recent Candidates -->
    <div class="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div class="p-6 border-b border-gray-100 flex justify-between items-center">
            <h3 class="font-bold text-slate-800 flex items-center"><i class="fa-solid fa-clock-rotate-left text-gray-400 mr-2"></i> Recent Candidates</h3>
            <a href="/candidates" class="text-sm text-blue-600 hover:underline">View All</a>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full text-sm text-left">
                <thead class="bg-gray-50 text-gray-500">
                    <tr>
                        <th class="p-4 font-medium">Name</th>
                        <th class="p-4 font-medium">Role</th>
                        <th class="p-4 font-medium">Score</th>
                        <th class="p-4 font-medium">Status</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                    {% for c in recent %}
                    <tr class="hover:bg-gray-50">
                        <td class="p-4 font-medium text-slate-700">{{ c.name }}</td>
                        <td class="p-4 text-gray-500">{{ c.matched_role }}</td>
                        <td class="p-4"><span class="font-bold {{ 'text-green-600' if c.score >= 75 else 'text-yellow-600' if c.score >= 50 else 'text-red-600' }}">{{ c.score }}%</span></td>
                        <td class="p-4">
                            <span class="px-2 py-1 rounded-full text-xs font-medium 
                                {% if c.status == 'Shortlisted' %}bg-green-100 text-green-700
                                {% elif c.status == 'On Hold' %}bg-yellow-100 text-yellow-700
                                {% else %}bg-red-100 text-red-700{% endif %}">
                                {{ c.status }}
                            </span>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="4" class="p-8 text-center text-gray-400">No candidates analyzed yet.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
"""

CONTENT_JOBS = """
<div class="flex justify-between items-center mb-6"><h2 class="text-3xl font-bold text-slate-800">Job Roles</h2><button onclick="document.getElementById('modal').classList.remove('hidden')" class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"><i class="fa-solid fa-plus mr-2"></i>Add Jobs (Bulk)</button></div>
<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
    {% for j in jobs %}
    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition relative group">
        <h3 class="text-xl font-bold text-slate-800 mb-2">{{ j.title }}</h3>
        <p class="text-gray-500 text-sm line-clamp-3 mb-4">{{ j.description }}</p>
        <form action="/delete_job" method="POST" onsubmit="return confirm('Delete this job?')" class="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition">
            <input type="hidden" name="id" value="{{ j.id }}"><button class="text-red-400 hover:text-red-600"><i class="fa-solid fa-trash"></i></button>
        </form>
    </div>
    {% endfor %}
</div>
<div id="modal" class="hidden fixed inset-0 bg-black/50 flex items-center justify-center z-50">
    <form action="/add_job" method="POST" enctype="multipart/form-data" class="bg-white p-8 rounded-xl w-96">
        <h3 class="text-xl font-bold mb-4">Upload PDFs</h3>
        <input type="file" name="files" multiple accept=".pdf" class="w-full border p-2 rounded mb-4">
        <div class="flex justify-end gap-2">
            <button type="button" onclick="document.getElementById('modal').classList.add('hidden')" class="text-gray-500 px-4">Cancel</button>
            <button class="bg-blue-600 text-white px-4 py-2 rounded">Upload</button>
        </div>
    </form>
</div>
"""

CONTENT_SCREEN = """
<div class="max-w-2xl mx-auto bg-white p-12 rounded-xl shadow-sm border border-gray-100 text-center mt-10">
    <div class="mb-6"><i class="fa-solid fa-cloud-arrow-up text-6xl text-blue-200"></i></div>
    <h2 class="text-2xl font-bold mb-2">AI Resume Screening</h2>
    <p class="text-gray-500 mb-8">Upload resumes to automatically match them against your jobs.</p>
    <form action="/process" method="POST" enctype="multipart/form-data">
        <label class="cursor-pointer bg-blue-50 text-blue-600 px-8 py-3 rounded-lg font-semibold hover:bg-blue-100 transition border border-blue-200 inline-block mb-4">
            <i class="fa-solid fa-file-pdf mr-2"></i> Select Files
            <input type="file" name="resumes" multiple accept=".pdf" class="hidden" onchange="this.form.submit()">
        </label>
        <p class="text-xs text-gray-400">Supported: Bulk PDF Upload</p>
    </form>
</div>
"""

CONTENT_CANDS = """
<div class="flex justify-between items-center mb-6">
    <h2 class="text-3xl font-bold text-slate-800">Candidates</h2>
    <a href="/export" class="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition flex items-center shadow-sm text-sm">
        <i class="fa-solid fa-file-csv mr-2"></i>Export CSV
    </a>
</div>

<form action="/candidates" method="GET" class="mb-6">
    <div class="relative max-w-md">
        <input type="text" name="q" placeholder="Search by name..." value="{{ request.args.get('q', '') }}" class="w-full p-2.5 pl-10 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 outline-none text-sm">
        <i class="fa-solid fa-magnifying-glass absolute left-3 top-3 text-gray-400 text-sm"></i>
    </div>
</form>

<div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
    <table class="w-full text-left">
        <thead class="bg-gray-50 border-b"><tr><th class="p-4">Name</th><th class="p-4">Role</th><th class="p-4">Score</th><th class="p-4">Status</th><th class="p-4 text-center">Actions</th></tr></thead>
        <tbody>
            {% for c in cands %}
            <tr class="hover:bg-gray-50 border-b border-gray-100">
                <td class="p-4 font-medium">
                    {{ c.name }}
                    <div class="text-xs text-gray-500">{{ c.email }}</div>
                    <div id="raw-{{c.id}}" class="hidden">{{ c.resume_text }}</div>
                </td>
                <td class="p-4">{{ c.matched_role }}</td>
                <td class="p-4"><span class="px-2 py-1 rounded text-xs font-bold {{ 'bg-green-100 text-green-700' if c.score>=75 else 'bg-yellow-100 text-yellow-700' if c.score>=50 else 'bg-red-100 text-red-700' }}">{{ c.score }}%</span></td>
                <td class="p-4">
                    <form action="/status" method="POST">
                        <input type="hidden" name="id" value="{{ c.id }}">
                        <select name="status" onchange="this.form.submit()" class="text-sm bg-transparent border-none cursor-pointer"><option {{ 'selected' if c.status=='Shortlisted' }}>Shortlisted</option><option {{ 'selected' if c.status=='On Hold' }}>On Hold</option><option {{ 'selected' if c.status=='Rejected' }}>Rejected</option></select>
                    </form>
                </td>
                <td class="p-4 flex gap-3 justify-center">
                    <button onclick="showResume('{{c.name}}', 'raw-{{c.id}}')" class="text-blue-500 hover:text-blue-700 transition" title="View Resume Text"><i class="fa-solid fa-eye"></i></button>
                    <form action="/del_cand" method="POST" onsubmit="return confirm('Delete?')"><input type="hidden" name="id" value="{{ c.id }}"><button class="text-red-400 hover:text-red-600 transition" title="Delete"><i class="fa-solid fa-trash"></i></button></form>
                </td>
            </tr>
            {% else %}
            <tr><td colspan="5" class="p-8 text-center text-gray-400">No candidates found.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<!-- View Resume Modal -->
<div id="viewModal" class="hidden fixed inset-0 bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm">
    <div class="bg-white rounded-xl w-3/4 max-w-4xl h-3/4 flex flex-col shadow-2xl animate-[fadeIn_0.2s_ease-out]">
        <div class="flex justify-between items-center p-6 border-b">
            <h3 class="text-xl font-bold text-slate-800 flex items-center">
                <i class="fa-solid fa-file-text text-blue-500 mr-2"></i>
                <span id="modalTitle">Resume</span>
            </h3>
            <button onclick="document.getElementById('viewModal').classList.add('hidden')" class="text-gray-400 hover:text-gray-600 transition"><i class="fa-solid fa-xmark text-xl"></i></button>
        </div>
        <div class="flex-1 overflow-y-auto bg-slate-50 p-6 m-4 rounded-lg border border-slate-200 font-mono text-xs md:text-sm whitespace-pre-wrap leading-relaxed text-slate-700 shadow-inner" id="modalContent"></div>
    </div>
</div>

<script>
function showResume(name, elementId) {
    const content = document.getElementById(elementId).innerText;
    document.getElementById('modalTitle').innerText = name;
    document.getElementById('modalContent').innerText = content;
    document.getElementById('viewModal').classList.remove('hidden');
}
</script>
"""

CONTENT_RANK = """
<h2 class="text-3xl font-bold text-slate-800 mb-6">Ranking</h2>
{% for role, group in grouped.items() %}
<div class="bg-white rounded-xl shadow-sm border border-gray-100 mb-6 overflow-hidden">
    <div class="bg-slate-50 p-4 border-b border-gray-200 flex justify-between"><h3 class="font-bold text-lg">{{ role }}</h3><span class="text-sm text-gray-500">{{ group|length }} Candidates</span></div>
    <div class="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div class="bg-green-50 p-3 rounded"><h4 class="text-green-800 font-bold text-sm mb-2">Shortlisted</h4>{% for c in group if c.status=='Shortlisted' %}<div class="bg-white p-2 rounded text-sm shadow-sm mb-1">{{ c.name }} ({{ c.score }}%)</div>{% endfor %}</div>
        <div class="bg-yellow-50 p-3 rounded"><h4 class="text-yellow-800 font-bold text-sm mb-2">On Hold</h4>{% for c in group if c.status=='On Hold' %}<div class="bg-white p-2 rounded text-sm shadow-sm mb-1">{{ c.name }} ({{ c.score }}%)</div>{% endfor %}</div>
        <div class="bg-red-50 p-3 rounded"><h4 class="text-red-800 font-bold text-sm mb-2">Rejected</h4>{% for c in group if c.status=='Rejected' %}<div class="bg-white p-2 rounded text-sm shadow-sm mb-1">{{ c.name }} ({{ c.score }}%)</div>{% endfor %}</div>
    </div>
</div>
{% endfor %}
"""

CONTENT_ADMIN = """
<h2 class="text-3xl font-bold text-slate-800 mb-6">Admin & Settings</h2>

<div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
    <!-- Profile Card -->
    <div class="bg-white p-8 rounded-xl shadow-sm border border-gray-100 text-center">
        <div class="w-24 h-24 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 text-4xl font-bold mx-auto mb-4">
            {{ user.email[0].upper() }}
        </div>
        <h3 class="text-xl font-bold text-slate-800">{{ user.email }}</h3>
        <p class="text-sm text-gray-500 mb-6">Administrator</p>
        <div class="bg-slate-50 p-4 rounded-lg text-left text-sm space-y-2 border border-slate-100">
            <div class="flex justify-between">
                <span class="text-gray-500">User ID:</span>
                <span class="font-mono text-xs text-slate-700">{{ user.id }}</span>
            </div>
            <div class="flex justify-between">
                <span class="text-gray-500">Account Type:</span>
                <span class="text-green-600 font-bold">Pro</span>
            </div>
        </div>
    </div>

    <!-- Stats & Quick Actions -->
    <div class="lg:col-span-2 space-y-6">
        <!-- Usage Stats -->
        <div class="grid grid-cols-2 gap-4">
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex items-center">
                <div class="p-3 bg-blue-50 text-blue-600 rounded-lg mr-4"><i class="fa-solid fa-briefcase text-xl"></i></div>
                <div>
                    <div class="text-2xl font-bold text-slate-800">{{ stats.jobs }}</div>
                    <div class="text-sm text-gray-500">Active Job Roles</div>
                </div>
            </div>
            <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex items-center">
                <div class="p-3 bg-purple-50 text-purple-600 rounded-lg mr-4"><i class="fa-solid fa-users text-xl"></i></div>
                <div>
                    <div class="text-2xl font-bold text-slate-800">{{ stats.cands }}</div>
                    <div class="text-sm text-gray-500">Total Candidates</div>
                </div>
            </div>
        </div>

        <!-- Settings / Danger Zone -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div class="p-4 border-b border-gray-100 bg-gray-50 font-semibold text-slate-700">Account Actions</div>
            <div class="p-6 space-y-4">
                <div class="flex items-center justify-between">
                    <div>
                        <h4 class="font-medium text-slate-800">Sign Out</h4>
                        <p class="text-sm text-gray-500">Log out of your account on this device.</p>
                    </div>
                    <a href="/logout" class="px-4 py-2 border border-gray-300 rounded-lg text-slate-600 hover:bg-gray-50 transition">Logout</a>
                </div>
                <div class="border-t border-gray-100 pt-4 flex items-center justify-between">
                    <div>
                        <h4 class="font-medium text-red-600">Delete Data</h4>
                        <p class="text-sm text-gray-500">Permanently remove all jobs and candidates.</p>
                    </div>
                    <form action="/delete_all_data" method="POST" onsubmit="return confirm('WARNING: This will delete ALL your jobs and candidates permanently. Are you sure?');">
                        <button type="submit" class="px-4 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition border border-red-200">Clear Data</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
</div>
"""

# ==========================================
# 4. LOGIC & HELPERS
# ==========================================

def render_view(content, is_public=False, **kwargs):
    layout = LAYOUT_AUTH if is_public else LAYOUT_APP
    return render_template_string(layout.replace('[[CONTENT]]', content), **kwargs)

def parse_pdf(f):
    try: return "".join([p.extract_text() for p in PdfReader(f).pages])
    except: return ""

def get_ai_score(t1, t2):
    if not t1 or not t2: return 0
    try: return round(cosine_similarity(TfidfVectorizer().fit_transform([t1, t2]))[0][1] * 100, 2)
    except: return 0

def get_details(txt):
    em = re.search(r'[\w.-]+@[\w.-]+', txt)
    return txt.split('\n')[0][:30], em.group(0) if em else "Unknown"

# ==========================================
# 5. ROUTES
# ==========================================

@app.before_request
def ensure_domain():
    if 'localhost' in request.host:
        return redirect(request.url.replace('localhost', '127.0.0.1'))

@app.route('/')
def index():
    return redirect('/dashboard') if 'user' in session else render_view(CONTENT_LOGIN, True)

# --- GOOGLE AUTH ---
@app.route('/login/google')
def google_auth():
    base_url = request.url_root.rstrip('/')
    if '127.0.0.1' not in base_url and 'localhost' not in base_url:
        base_url = base_url.replace('http://', 'https://')
        
    callback = f"{base_url}/auth/callback"
    print(f"DEBUG: Redirecting to Supabase with callback: {callback}")
    
    res = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {"redirect_to": callback}
    })
    return redirect(res.url)

@app.route('/auth/callback')
def auth_callback_page():
    # Handle PKCE flow (Authorization Code) - The modern/default Supabase flow
    code = request.args.get('code')
    if code:
        try:
            # Exchange the code for a session
            res = supabase.auth.exchange_code_for_session({"auth_code": code})
            user = res.user
            
            if user:
                session.clear()
                session['user'] = {'id': user.id, 'email': user.email}
                session.permanent = True
                return redirect('/dashboard')
        except Exception as e:
            # If exchange fails, show error
            return f"<h1>Login Error</h1><p>Failed to exchange code: {str(e)}</p><a href='/'>Return to Login</a>"

    # Handle Implicit flow (Access Token in Hash) - Legacy or specific config
    # This renders the JS page which parses the #hash
    return render_view(CONTENT_CALLBACK, True)

@app.route('/auth/confirm', methods=['POST'])
def confirm_auth():
    try:
        data = request.json
        user = supabase.auth.get_user(data['access_token']).user
        if user:
            session.clear()
            session['user'] = {'id': user.id, 'email': user.email}
            session.permanent = True
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "Invalid Token"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# --- STANDARD AUTH ---
@app.route('/login', methods=['POST'])
def login():
    try:
        r = supabase.auth.sign_in_with_password({"email": request.form['email'], "password": request.form['password']})
        session['user'] = {'id': r.user.id, 'email': r.user.email}
        return redirect('/dashboard')
    except Exception as e:
        flash(f"Error: {e}", "error")
        return redirect('/')

@app.route('/signup', methods=['POST'])
def signup():
    try:
        supabase.auth.sign_up({"email": request.form['email'], "password": request.form['password']})
        flash("Signup Success! Please Login.", "success")
        return redirect('/')
    except Exception as e:
        flash(f"Error: {e}", "error")
        return redirect('/')

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

# --- APP LOGIC ---
@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect('/')
    uid = session['user']['id']
    
    # Fetch recent candidates (limit 5)
    try:
        recent = supabase.table('candidates').select('*').eq('user_id', uid).order('created_at', desc=True).limit(5).execute().data
    except:
        recent = []

    stats = {
        'jobs': supabase.table('job_roles').select('*', count='exact').eq('user_id', uid).execute().count,
        'cands': supabase.table('candidates').select('*', count='exact').eq('user_id', uid).execute().count,
        'short': len(supabase.table('candidates').select('*').eq('user_id', uid).eq('status', 'Shortlisted').execute().data),
        'avg': 0
    }
    
    # Avg score logic
    all_cands_scores = supabase.table('candidates').select('score').eq('user_id', uid).execute().data
    if all_cands_scores: 
        stats['avg'] = round(sum(c['score'] for c in all_cands_scores)/len(all_cands_scores), 1)
    
    return render_view(CONTENT_DASHBOARD, stats=stats, recent=recent)

@app.route('/job_roles')
def jobs():
    if 'user' not in session: return redirect('/')
    d = supabase.table('job_roles').select('*').eq('user_id', session['user']['id']).execute().data
    return render_view(CONTENT_JOBS, jobs=d)

@app.route('/add_job', methods=['POST'])
def add_job():
    if 'user' not in session: return redirect('/')
    
    # Debug: print user id to verify
    print(f"DEBUG: Adding job for User ID: {session['user']['id']}")
    
    for f in request.files.getlist('files'):
        txt = parse_pdf(f)
        if txt: 
            try:
                supabase.table('job_roles').insert({'user_id': session['user']['id'], 'title': f.filename, 'description': txt}).execute()
            except Exception as e:
                print(f"DEBUG: Error inserting job: {e}")
                flash(f"Error adding job: {str(e)}", "error")
                return redirect('/job_roles')
                
    return redirect('/job_roles')

@app.route('/delete_job', methods=['POST'])
def del_job():
    supabase.table('candidates').delete().eq('job_role_id', request.form['id']).execute()
    supabase.table('job_roles').delete().eq('id', request.form['id']).execute()
    return redirect('/job_roles')

@app.route('/ai_screening')
def screen(): return render_view(CONTENT_SCREEN) if 'user' in session else redirect('/')

@app.route('/process', methods=['POST'])
def process():
    if 'user' not in session: return redirect('/')
    uid = session['user']['id']
    jobs = supabase.table('job_roles').select('*').eq('user_id', uid).execute().data
    if not jobs:
        flash("Add Jobs first!", "error")
        return redirect('/job_roles')
    
    for f in request.files.getlist('resumes'):
        txt = parse_pdf(f)
        if not txt: continue
        best_j, best_s = None, -1
        for j in jobs:
            s = get_ai_score(txt, j['description'])
            if s > best_s: best_s, best_j = s, j
        
        if best_j:
            nm, em = get_details(txt)
            st = 'Shortlisted' if best_s>=75 else 'On Hold' if best_s>=50 else 'Rejected'
            supabase.table('candidates').insert({'user_id': uid, 'name': nm, 'email': em, 'job_role_id': best_j['id'], 'matched_role': best_j['title'], 'score': best_s, 'status': st, 'resume_text': txt[:5000]}).execute()
    return redirect('/candidates')

@app.route('/candidates')
def cands():
    if 'user' not in session: return redirect('/')
    query = supabase.table('candidates').select('*').eq('user_id', session['user']['id']).order('score', desc=True)
    
    search_term = request.args.get('q')
    if search_term:
        query = query.ilike('name', f'%{search_term}%')
        
    d = query.execute().data
    return render_view(CONTENT_CANDS, cands=d)

@app.route('/status', methods=['POST'])
def status():
    supabase.table('candidates').update({'status': request.form['status']}).eq('id', request.form['id']).execute()
    return redirect('/candidates')

@app.route('/del_cand', methods=['POST'])
def del_cand():
    supabase.table('candidates').delete().eq('id', request.form['id']).execute()
    return redirect('/candidates')

@app.route('/ranking')
def ranking():
    if 'user' not in session: return redirect('/')
    d = supabase.table('candidates').select('*').eq('user_id', session['user']['id']).execute().data
    g = {}
    for c in d: g.setdefault(c['matched_role'], []).append(c)
    return render_view(CONTENT_RANK, grouped=g)

@app.route('/export')
def export_csv():
    if 'user' not in session: return redirect('/')
    data = supabase.table('candidates').select('*').eq('user_id', session['user']['id']).execute().data
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Name', 'Email', 'Role', 'Score', 'Status', 'Extracted Text'])
    for c in data:
        cw.writerow([c.get('name'), c.get('email'), c.get('matched_role'), c.get('score'), c.get('status'), c.get('resume_text', '')[:100]+'...'])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=candidates.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/delete_all_data', methods=['POST'])
def delete_all_data():
    if 'user' not in session: return redirect('/')
    uid = session['user']['id']
    try:
        # Delete related candidates first
        supabase.table('candidates').delete().eq('user_id', uid).execute()
        # Then delete jobs
        supabase.table('job_roles').delete().eq('user_id', uid).execute()
        flash("All data successfully cleared.", "success")
    except Exception as e:
        flash(f"Error clearing data: {str(e)}", "error")
    return redirect('/admin')

@app.route('/admin')
def admin():
    if 'user' not in session: return redirect('/')
    uid = session['user']['id']
    try:
        job_count = supabase.table('job_roles').select('*', count='exact').eq('user_id', uid).execute().count
        cand_count = supabase.table('candidates').select('*', count='exact').eq('user_id', uid).execute().count
    except:
        job_count = 0
        cand_count = 0
    
    return render_view(CONTENT_ADMIN, user=session['user'], stats={'jobs': job_count, 'cands': cand_count})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

