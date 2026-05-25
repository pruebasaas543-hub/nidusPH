"""
app/configuracion/apariencias/model.py
"""

from app import db
from datetime import datetime
from bson import ObjectId


def _col():
    return db["apariencias"]


# ── CSS completo de cada tema ─────────────────────────────────────────────────

_CSS = {
    "default": """html[data-tema="default"] *[style*="color:rgba(0,212,255"]{color:rgba(18,96,196,.65)!important}
html[data-tema="default"] *[style*="color:#00c8f0"]{color:rgba(18,96,196,.65)!important}
html[data-tema="default"] *[style*="color:rgba(255,255,255"]{color:rgba(4,34,67,.35)!important}""",

    "oscuro-cyan": """html[data-tema="oscuro-cyan"] body{background:#0B0F17;color:#F8FAFC}
html[data-tema="oscuro-cyan"] .topbar{background:#111827;border-bottom:1px solid #1F2937;box-shadow:0 4px 20px rgba(0,0,0,.5)}
html[data-tema="oscuro-cyan"] .sidebar{background:#111827;border-right:1px solid #1F2937}
html[data-tema="oscuro-cyan"] .main-content{background:#0B0F17}
html[data-tema="oscuro-cyan"] .sidebar-section-title{color:rgba(255,255,255,.5)}
html[data-tema="oscuro-cyan"] .nav-item{color:rgba(255,255,255,.75)}
html[data-tema="oscuro-cyan"] .nav-item:hover{color:white;background:rgba(255,255,255,.12);border-left-color:rgba(255,255,255,.5)}
html[data-tema="oscuro-cyan"] .nav-item.active{color:#FFFFFF;background:rgba(6,182,212,.15);border-left-color:#06B6D4}
html[data-tema="oscuro-cyan"] .config-group-label{color:rgba(255,255,255,.9)}
html[data-tema="oscuro-cyan"] .config-group-arrow{color:rgba(255,255,255,.5)}
html[data-tema="oscuro-cyan"] .sidebar-config-header:hover{background:rgba(255,255,255,.07)}
html[data-tema="oscuro-cyan"] .config-section-divider{background:rgba(255,255,255,.15)}
html[data-tema="oscuro-cyan"] .config-panel-title{color:#F8FAFC}
html[data-tema="oscuro-cyan"] .config-panel-title span{color:#CFFAFE}
html[data-tema="oscuro-cyan"] .config-panel-subtitle{color:#6B7280}
html[data-tema="oscuro-cyan"] .config-form-card{background:#1F2937;border-color:#374151;box-shadow:0 4px 20px rgba(0,0,0,.2)}
html[data-tema="oscuro-cyan"] .config-form-card-title{color:#F8FAFC;border-bottom-color:#374151}
html[data-tema="oscuro-cyan"] .form-group label{color:#E2F8FF}
html[data-tema="oscuro-cyan"] .form-control{background:#111827;border-color:#4B5563;color:#fff}
html[data-tema="oscuro-cyan"] .form-control:focus{border-color:#06B6D4;background:#111827;box-shadow:0 0 0 3px rgba(6,182,212,.25)}
html[data-tema="oscuro-cyan"] .form-control::placeholder{color:#4B5563}
html[data-tema="oscuro-cyan"] select.form-control{background-color:#111827!important;color-scheme:dark}
html[data-tema="oscuro-cyan"] select.form-control option{background:#111827;color:#fff}
html[data-tema="oscuro-cyan"] .custom-dropdown-btn{background:#111827;border-color:#4B5563;color:#fff}
html[data-tema="oscuro-cyan"] .custom-dropdown-menu{background:#1F2937;border-color:#374151}
html[data-tema="oscuro-cyan"] .custom-dropdown-item:hover{background:rgba(6,182,212,.08)}
html[data-tema="oscuro-cyan"] .custom-dropdown-item label{color:#F8FAFC;cursor:pointer}
html[data-tema="oscuro-cyan"] .custom-dropdown-item input[type="checkbox"]{accent-color:#06B6D4}
html[data-tema="oscuro-cyan"] .cd-item-text{color:#F8FAFC}
html[data-tema="oscuro-cyan"] .cd-item-row:hover{background:rgba(6,182,212,.08)}
html[data-tema="oscuro-cyan"] .cd-item-check{accent-color:#06B6D4}
html[data-tema="oscuro-cyan"] .horario-col-header{color:#E2F8FF}
html[data-tema="oscuro-cyan"] .horario-dia-nombre{color:#E2F8FF}
html[data-tema="oscuro-cyan"] .cd-label{color:rgba(255,255,255,.4)}
html[data-tema="oscuro-cyan"] .cd-label.has-sel{color:#fff}
html[data-tema="oscuro-cyan"] .ptab{background:#111827;border-color:#374151;color:#9CA3AF}
html[data-tema="oscuro-cyan"] .ptab:hover{color:#fff;background:#1F2937;border-color:#4B5563}
html[data-tema="oscuro-cyan"] .ptab.active{background:#06B6D4;border-color:#06B6D4;color:#0B0F17;box-shadow:0 4px 14px rgba(6,182,212,.4)}
html[data-tema="oscuro-cyan"] .btn-primary{background:linear-gradient(135deg,#06B6D4,#0284C7);color:#0B0F17}
html[data-tema="oscuro-cyan"] .btn-primary:hover{box-shadow:0 8px 24px rgba(6,182,212,.4)}
html[data-tema="oscuro-cyan"] .btn-secondary{background:#111827;border-color:#374151;color:#9CA3AF}
html[data-tema="oscuro-cyan"] .btn-secondary:hover{background:#1F2937;border-color:#06B6D4;color:#06B6D4}
html[data-tema="oscuro-cyan"] .btn-icon-edit{background:rgba(6,182,212,.1);color:#CFFAFE}
html[data-tema="oscuro-cyan"] .data-table th{color:#E2F8FF;border-bottom-color:#374151}
html[data-tema="oscuro-cyan"] .data-table td{color:#D1D5DB;border-bottom-color:#1F2937}
html[data-tema="oscuro-cyan"] .data-table tr:hover td{background:rgba(6,182,212,.05)}
html[data-tema="oscuro-cyan"] .data-table-empty{color:#6B7280}
html[data-tema="oscuro-cyan"] .table-search{background:#1F2937;border-color:#374151}
html[data-tema="oscuro-cyan"] .table-search input{color:#fff}
html[data-tema="oscuro-cyan"] .spinner{border-color:rgba(6,182,212,.2);border-top-color:#06B6D4}
html[data-tema="oscuro-cyan"] .modal-overlay{background:rgba(0,0,0,.65)}
html[data-tema="oscuro-cyan"] .modal-box{background:#1F2937;border-color:#374151;color:#F8FAFC}
html[data-tema="oscuro-cyan"] .modal-title{color:#E2F8FF}
html[data-tema="oscuro-cyan"] .modal-confirmacion-dialog{background:#1F2937;border-color:#374151}
html[data-tema="oscuro-cyan"] .modal-confirmacion-title{color:#E2F8FF}
html[data-tema="oscuro-cyan"] .modal-confirmacion-message{color:#D1D5DB}
html[data-tema="oscuro-cyan"] .modal-confirmacion-btn{border-color:#374151;background:rgba(6,182,212,.08);color:#CFFAFE}
html[data-tema="oscuro-cyan"] .info-box{background:rgba(6,182,212,.07);border-color:rgba(6,182,212,.2);color:#9CA3AF}
html[data-tema="oscuro-cyan"] .info-box strong{color:#E2F8FF}
html[data-tema="oscuro-cyan"] .modulo-check{background:rgba(255,255,255,.04);border-color:#374151}
html[data-tema="oscuro-cyan"] .modulo-check label{color:#D1D5DB}
html[data-tema="oscuro-cyan"] .plan-card{background:#1F2937;border-color:#374151}
html[data-tema="oscuro-cyan"] .plan-card h3{color:#F8FAFC}
html[data-tema="oscuro-cyan"] .plan-card .precio{color:#CFFAFE}
html[data-tema="oscuro-cyan"] .pago-card{background:#1F2937;border-color:#374151}
html[data-tema="oscuro-cyan"] .pago-card-title{color:#F8FAFC}
html[data-tema="oscuro-cyan"] .upload-zone{border-color:rgba(6,182,212,.3)}
html[data-tema="oscuro-cyan"] .theme-card-info{background:rgba(31,41,55,.95)}
html[data-tema="oscuro-cyan"] .theme-card-name{color:#F8FAFC}
html[data-tema="oscuro-cyan"] .theme-card-desc{color:#6B7280}
html[data-tema="oscuro-cyan"] .ptab.active{background-color:#06B6D4!important;color:#0B0F17!important}
html[data-tema="oscuro-cyan"] .horario-col-header,html[data-tema="oscuro-cyan"] .horario-dia-nombre{color:#E2F8FF!important}
html[data-tema="oscuro-cyan"] *[style*="color:#042243"]{color:#D7F3F5!important}
html[data-tema="oscuro-cyan"] *[style*="color:#1E2756"]{color:#D7F3F5!important}
html[data-tema="oscuro-cyan"] *[style*="color:rgba(4,34,67"]{color:rgba(199,219,242,.75)!important}
html[data-tema="oscuro-cyan"] *[style*="color:rgba(30,39,86"]{color:rgba(215,243,245,.7)!important}
html[data-tema="oscuro-cyan"] *[style*="color:#6B7AAD"]{color:#C7DBF2!important}
html[data-tema="oscuro-cyan"] *[style*="color:#999"]{color:rgba(199,219,242,.5)!important}""",

    "bosque": """html[data-tema="bosque"] body{background:#F3F4F6;color:#111827}
html[data-tema="bosque"] .topbar{background:#111827;border-bottom:1px solid rgba(255,255,255,.1)}
html[data-tema="bosque"] .sidebar{background:#111827;border-right:1px solid rgba(255,255,255,.1)}
html[data-tema="bosque"] .main-content{background:#F3F4F6}
html[data-tema="bosque"] .sidebar-section-title{color:rgba(255,255,255,.5)}
html[data-tema="bosque"] .nav-item{color:rgba(255,255,255,.75)}
html[data-tema="bosque"] .nav-item:hover{color:white;background:rgba(255,255,255,.12);border-left-color:rgba(255,255,255,.5)}
html[data-tema="bosque"] .nav-item.active{color:white;background:rgba(255,255,255,.22);border-left-color:#606C5D}
html[data-tema="bosque"] .config-group-label{color:rgba(255,255,255,.9)}
html[data-tema="bosque"] .config-group-arrow{color:rgba(255,255,255,.5)}
html[data-tema="bosque"] .sidebar-config-header:hover{background:rgba(255,255,255,.07)}
html[data-tema="bosque"] .config-section-divider{background:rgba(255,255,255,.15)}
html[data-tema="bosque"] .config-panel-title{color:#212529}
html[data-tema="bosque"] .config-panel-title span{color:#606C5D}
html[data-tema="bosque"] .config-panel-subtitle{color:#6B7280}
html[data-tema="bosque"] .config-form-card{background:#FFFFFF;border-color:#E5E7EB;box-shadow:0 2px 8px rgba(0,0,0,.05)}
html[data-tema="bosque"] .config-form-card-title{color:#212529;border-bottom-color:#E5E7EB}
html[data-tema="bosque"] .form-group label{color:#606C5D}
html[data-tema="bosque"] .form-control{background:#F9FAFB;border-color:#D1D5DB;color:#111827}
html[data-tema="bosque"] .form-control:focus{border-color:#606C5D;box-shadow:0 0 0 3px rgba(96,108,93,.15)}
html[data-tema="bosque"] select.form-control{background-color:#F9FAFB!important;color-scheme:light}
html[data-tema="bosque"] .custom-dropdown-btn{background:#F9FAFB;border-color:#D1D5DB;color:#111827}
html[data-tema="bosque"] .custom-dropdown-menu{background:#fff;border-color:#D1D5DB}
html[data-tema="bosque"] .cd-item-text{color:#111827}
html[data-tema="bosque"] .ptab{background:#FFFFFF;border-color:#E5E7EB;color:#6B7280}
html[data-tema="bosque"] .ptab:hover{color:#111827;background:#F3F4F6}
html[data-tema="bosque"] .ptab.active{background:#606C5D;border-color:#606C5D;color:white;box-shadow:0 4px 14px rgba(96,108,93,.3)}
html[data-tema="bosque"] .btn-primary{background:linear-gradient(135deg,#606C5D,#4A5548);color:white}
html[data-tema="bosque"] .btn-primary:hover{box-shadow:0 8px 24px rgba(96,108,93,.3)}
html[data-tema="bosque"] .btn-secondary{background:#fff;border-color:#D1D5DB;color:#4B5563}
html[data-tema="bosque"] .btn-secondary:hover{border-color:#606C5D;color:#606C5D}
html[data-tema="bosque"] .data-table th{color:#606C5D;border-bottom-color:#E5E7EB}
html[data-tema="bosque"] .data-table td{color:#374151;border-bottom-color:#F3F4F6}
html[data-tema="bosque"] .data-table tr:hover td{background:rgba(96,108,93,.04)}
html[data-tema="bosque"] .table-search{background:#fff;border-color:#E5E7EB}
html[data-tema="bosque"] .table-search input{color:#111827}
html[data-tema="bosque"] .spinner{border-color:rgba(96,108,93,.2);border-top-color:#606C5D}
html[data-tema="bosque"] .modal-box{background:#fff;border-color:#E5E7EB;color:#111827}
html[data-tema="bosque"] .modal-title{color:#606C5D}
html[data-tema="bosque"] .modal-confirmacion-dialog{background:#fff;border-color:#E5E7EB}
html[data-tema="bosque"] .modal-confirmacion-title{color:#606C5D}
html[data-tema="bosque"] .modal-confirmacion-message{color:#374151}
html[data-tema="bosque"] .modal-confirmacion-btn{border-color:#E5E7EB;background:rgba(96,108,93,.06);color:#606C5D}
html[data-tema="bosque"] .info-box{background:rgba(96,108,93,.06);border-color:rgba(96,108,93,.2);color:#4B5563}
html[data-tema="bosque"] .info-box strong{color:#606C5D}
html[data-tema="bosque"] .modulo-check{background:#fff;border-color:rgba(96,108,93,.2)}
html[data-tema="bosque"] .modulo-check label{color:#374151}
html[data-tema="bosque"] .plan-card{background:#fff;border-color:rgba(96,108,93,.2)}
html[data-tema="bosque"] .plan-card h3{color:#111827}
html[data-tema="bosque"] .plan-card .precio{color:#606C5D}
html[data-tema="bosque"] .pago-card{background:#fff;border-color:#E5E7EB}
html[data-tema="bosque"] .pago-card-title{color:#111827}
html[data-tema="bosque"] .horario-dia-nombre,html[data-tema="bosque"] .horario-col-header{color:#606C5D!important}
html[data-tema="bosque"] .theme-card-name{color:#111827!important}
html[data-tema="bosque"] .theme-card-desc{color:#6B7280!important}
html[data-tema="bosque"] .cd-label{color:rgba(17,24,37,0.6)!important}
html[data-tema="bosque"] *[style*="color:rgba(0,212,255"]{color:#606C5D!important}
html[data-tema="bosque"] *[style*="color:#00c8f0"]{color:#606C5D!important}
html[data-tema="bosque"] *[style*="color:rgba(255,255,255"]{color:rgba(96,108,93,.5)!important}
html[data-tema="bosque"] *[style*="color:#999"]{color:rgba(96,108,93,.45)!important}""",

    "galaxia": """html[data-tema="galaxia"] body{background:#090D16;color:#F5EFE9}
html[data-tema="galaxia"] .topbar{background:#0F1524;border-bottom:1px solid #1E293B}
html[data-tema="galaxia"] .sidebar{background:#0F1524;border-right:1px solid #1E293B}
html[data-tema="galaxia"] .main-content{background:#090D16}
html[data-tema="galaxia"] .sidebar-section-title{color:rgba(245,239,233,.55)}
html[data-tema="galaxia"] .nav-item{color:rgba(245,239,233,.8)}
html[data-tema="galaxia"] .nav-item:hover{color:#F5EFE9;background:rgba(255,255,255,.15);border-left-color:rgba(255,255,255,.6)}
html[data-tema="galaxia"] .nav-item.active{color:#F5EFE9;background:rgba(255,255,255,.22);border-left-color:#F5E9EF}
html[data-tema="galaxia"] .config-group-label{color:rgba(245,239,233,.9)}
html[data-tema="galaxia"] .config-group-arrow{color:rgba(245,239,233,.5)}
html[data-tema="galaxia"] .sidebar-config-header:hover{background:rgba(255,255,255,.05)}
html[data-tema="galaxia"] .config-section-divider{background:rgba(255,255,255,.1)}
html[data-tema="galaxia"] .config-panel-title{color:#F5EFE9}
html[data-tema="galaxia"] .config-panel-title span{color:#F5E9EF}
html[data-tema="galaxia"] .config-panel-subtitle{color:rgba(245,239,233,.65)}
html[data-tema="galaxia"] .config-form-card{background:#151D30;border-color:#24324F;box-shadow:0 4px 20px rgba(0,0,0,.3)}
html[data-tema="galaxia"] .config-form-card-title{color:#F5EFE9;border-bottom-color:#24324F}
html[data-tema="galaxia"] .form-group label{color:#F5E9EF}
html[data-tema="galaxia"] .form-control{background:#0F1524;border-color:#24324F;color:#F5EFE9}
html[data-tema="galaxia"] .form-control:focus{border-color:#FB7185;background:#0F1524;box-shadow:0 0 0 3px rgba(251,113,133,.2)}
html[data-tema="galaxia"] select.form-control{background-color:#0F1524!important;color-scheme:dark}
html[data-tema="galaxia"] select.form-control option{background:#0F1524;color:#F5EFE9}
html[data-tema="galaxia"] .custom-dropdown-btn{background:#0F1524;border-color:#24324F;color:#F5EFE9}
html[data-tema="galaxia"] .custom-dropdown-menu{background:#151D30;border-color:#24324F}
html[data-tema="galaxia"] .custom-dropdown-item label{color:#F5EFE9;cursor:pointer}
html[data-tema="galaxia"] .custom-dropdown-item:hover{background:rgba(251,113,133,.08)}
html[data-tema="galaxia"] .custom-dropdown-item input[type="checkbox"]{accent-color:#FB7185}
html[data-tema="galaxia"] .cd-item-text{color:#F5EFE9}
html[data-tema="galaxia"] .cd-item-row:hover{background:rgba(251,113,133,.08)}
html[data-tema="galaxia"] .cd-item-check{accent-color:#FB7185}
html[data-tema="galaxia"] .horario-col-header{color:#F5E9EF}
html[data-tema="galaxia"] .horario-dia-nombre{color:#F5E9EF}
html[data-tema="galaxia"] .cd-label{color:rgba(245,233,239,.55)}
html[data-tema="galaxia"] .cd-label.has-sel{color:#F5EFE9}
html[data-tema="galaxia"] .ptab{background:#0F1524;border-color:#24324F;color:rgba(245,239,233,.7)}
html[data-tema="galaxia"] .ptab:hover{color:#F5EFE9;background:#151D30;border-color:#FB7185}
html[data-tema="galaxia"] .ptab.active{background:linear-gradient(135deg,#FB7185,#F43F5E);border-color:#F43F5E;color:#F5EFE9;box-shadow:0 4px 14px rgba(251,113,133,.35)}
html[data-tema="galaxia"] .btn-primary{background:linear-gradient(135deg,#FB7185,#E11D48);color:#F5EFE9}
html[data-tema="galaxia"] .btn-primary:hover{box-shadow:0 8px 24px rgba(251,113,133,.4)}
html[data-tema="galaxia"] .btn-secondary{background:#0F1524;border-color:#24324F;color:rgba(245,239,233,.75)}
html[data-tema="galaxia"] .btn-secondary:hover{background:#151D30;border-color:#FB7185;color:#F5E9EF}
html[data-tema="galaxia"] .data-table th{color:#F5E9EF;border-bottom-color:#24324F}
html[data-tema="galaxia"] .data-table td{color:#F5EFE9;border-bottom-color:#151D30}
html[data-tema="galaxia"] .data-table tr:hover td{background:rgba(251,113,133,.04)}
html[data-tema="galaxia"] .table-search{background:#151D30;border-color:#24324F}
html[data-tema="galaxia"] .table-search input{color:#F5EFE9}
html[data-tema="galaxia"] .table-search input::placeholder{color:rgba(245,239,233,.35)}
html[data-tema="galaxia"] .spinner{border-color:rgba(251,113,133,.2);border-top-color:#FB7185}
html[data-tema="galaxia"] .modal-overlay{background:rgba(0,0,0,.7)}
html[data-tema="galaxia"] .modal-box{background:#151D30;border-color:#24324F;color:#F5EFE9}
html[data-tema="galaxia"] .modal-title{color:#F5E9EF}
html[data-tema="galaxia"] .modal-confirmacion-dialog{background:#151D30;border-color:#24324F}
html[data-tema="galaxia"] .modal-confirmacion-title{color:#F5E9EF}
html[data-tema="galaxia"] .modal-confirmacion-message{color:rgba(245,239,233,.85)}
html[data-tema="galaxia"] .modal-confirmacion-btn{border-color:#24324F;background:rgba(251,113,133,.08);color:#F5E9EF}
html[data-tema="galaxia"] .info-box{background:rgba(251,113,133,.08);border-color:rgba(251,113,133,.2);color:rgba(245,239,233,.8)}
html[data-tema="galaxia"] .info-box strong{color:#F5E9EF}
html[data-tema="galaxia"] .modulo-check{background:rgba(255,255,255,.03);border-color:#24324F}
html[data-tema="galaxia"] .modulo-check label{color:rgba(245,239,233,.85)}
html[data-tema="galaxia"] .plan-card{background:#151D30;border-color:#24324F}
html[data-tema="galaxia"] .plan-card h3{color:#F5EFE9}
html[data-tema="galaxia"] .plan-card .precio{color:#F5E9EF}
html[data-tema="galaxia"] .pago-card{background:#151D30;border-color:#24324F}
html[data-tema="galaxia"] .pago-card-title{color:#F5EFE9}
html[data-tema="galaxia"] .theme-card-info{background:rgba(21,29,48,.95)}
html[data-tema="galaxia"] .theme-card-name{color:#F5EFE9}
html[data-tema="galaxia"] .theme-card-desc{color:rgba(245,239,233,.65)}
html[data-tema="galaxia"] .data-table-empty{color:rgba(245,239,233,.45)}
html[data-tema="galaxia"] .btn-primary{background-color:#FB7185!important;color:#F5EFE9!important}
html[data-tema="galaxia"] .ptab.active{background-color:#FB7185!important;color:#F5EFE9!important}
html[data-tema="galaxia"] .desc-short{color:rgba(245,239,233,.75)!important}
html[data-tema="galaxia"] .desc-full{color:rgba(245,239,233,.75)!important}
html[data-tema="galaxia"] .desc-toggle{color:#F5E9EF!important}
html[data-tema="galaxia"] *[style*="color:#042243"]{color:#F5EFE9!important}
html[data-tema="galaxia"] *[style*="color:#1E2756"]{color:#F5EFE9!important}
html[data-tema="galaxia"] *[style*="color:rgba(4,34,67"]{color:rgba(245,239,233,.7)!important}
html[data-tema="galaxia"] *[style*="color:rgba(30,39,86"]{color:rgba(245,239,233,.7)!important}
html[data-tema="galaxia"] *[style*="color:rgba(0,212,255"]{color:#F5E9EF!important}
html[data-tema="galaxia"] *[style*="color:#00c8f0"]{color:#F5E9EF!important}
html[data-tema="galaxia"] *[style*="color:#6B7AAD"]{color:rgba(245,239,233,.7)!important}
html[data-tema="galaxia"] *[style*="color:#999"]{color:rgba(245,239,233,.5)!important}""",

    "grafito": """html[data-tema="grafito"] body{background:#F1F3F5;color:#2B303A}
html[data-tema="grafito"] .topbar{background:#212529;border-bottom:1px solid #343A40}
html[data-tema="grafito"] .sidebar{background:#212529;border-right:1px solid #343A40}
html[data-tema="grafito"] .main-content{background:#F1F3F5}
html[data-tema="grafito"] .sidebar-section-title{color:rgba(255,255,255,.45)}
html[data-tema="grafito"] .nav-item{color:rgba(255,255,255,.7)}
html[data-tema="grafito"] .nav-item:hover{color:white;background:rgba(255,255,255,.12);border-left-color:rgba(255,255,255,.4)}
html[data-tema="grafito"] .nav-item.active{color:white;background:rgba(255,255,255,.2);border-left-color:#606C5D}
html[data-tema="grafito"] .config-group-label{color:rgba(255,255,255,.9)}
html[data-tema="grafito"] .config-group-arrow{color:rgba(255,255,255,.45)}
html[data-tema="grafito"] .sidebar-config-header:hover{background:rgba(255,255,255,.07)}
html[data-tema="grafito"] .config-section-divider{background:rgba(255,255,255,.12)}
html[data-tema="grafito"] .config-panel-title{color:#212529}
html[data-tema="grafito"] .config-panel-title span{color:#606C5D}
html[data-tema="grafito"] .config-panel-subtitle{color:#6B7280}
html[data-tema="grafito"] .config-form-card{background:#FFFFFF;border-color:#D8DDE5;box-shadow:0 2px 8px rgba(0,0,0,.04)}
html[data-tema="grafito"] .config-form-card-title{color:#212529;border-bottom-color:#E5E8ED}
html[data-tema="grafito"] .form-group label{color:#606C5D}
html[data-tema="grafito"] .form-control{background:#F8F9FA;border-color:#CED4DA;color:#2B303A}
html[data-tema="grafito"] .form-control:focus{border-color:#606C5D;box-shadow:0 0 0 3px rgba(96,108,93,.12)}
html[data-tema="grafito"] select.form-control{background-color:#F8F9FA!important;color-scheme:light}
html[data-tema="grafito"] .custom-dropdown-btn{background:#F8F9FA;border-color:#CED4DA;color:#2B303A}
html[data-tema="grafito"] .custom-dropdown-menu{background:#fff;border-color:#CED4DA}
html[data-tema="grafito"] .cd-item-text{color:#2B303A}
html[data-tema="grafito"] .ptab{background:#fff;border-color:#D8DDE5;color:#6B7280}
html[data-tema="grafito"] .ptab:hover{color:#212529;background:#F1F3F5}
html[data-tema="grafito"] .ptab.active{background:#606C5D;border-color:#606C5D;color:white;box-shadow:0 4px 14px rgba(96,108,93,.3)}
html[data-tema="grafito"] .btn-primary{background:linear-gradient(135deg,#606C5D,#4A5548);color:white}
html[data-tema="grafito"] .btn-primary:hover{box-shadow:0 8px 24px rgba(96,108,93,.3)}
html[data-tema="grafito"] .btn-secondary{background:#fff;border-color:#CED4DA;color:#6B7280}
html[data-tema="grafito"] .btn-secondary:hover{border-color:#606C5D;color:#606C5D}
html[data-tema="grafito"] .data-table th{color:#606C5D;border-bottom-color:#D8DDE5}
html[data-tema="grafito"] .data-table td{color:#374151;border-bottom-color:#EEF0F3}
html[data-tema="grafito"] .data-table tr:hover td{background:rgba(96,108,93,.04)}
html[data-tema="grafito"] .table-search{background:#fff;border-color:#D8DDE5}
html[data-tema="grafito"] .table-search input{color:#2B303A}
html[data-tema="grafito"] .spinner{border-color:rgba(96,108,93,.2);border-top-color:#606C5D}
html[data-tema="grafito"] .modal-box{background:#fff;border-color:#D8DDE5;color:#2B303A}
html[data-tema="grafito"] .modal-title{color:#606C5D}
html[data-tema="grafito"] .modal-confirmacion-dialog{background:#fff;border-color:#D8DDE5}
html[data-tema="grafito"] .modal-confirmacion-title{color:#606C5D}
html[data-tema="grafito"] .modal-confirmacion-message{color:#374151}
html[data-tema="grafito"] .modal-confirmacion-btn{border-color:#D8DDE5;background:rgba(96,108,93,.06);color:#606C5D}
html[data-tema="grafito"] .info-box{background:rgba(96,108,93,.06);border-color:rgba(96,108,93,.18);color:#4B5563}
html[data-tema="grafito"] .info-box strong{color:#606C5D}
html[data-tema="grafito"] .modulo-check{background:#fff;border-color:rgba(96,108,93,.18)}
html[data-tema="grafito"] .modulo-check label{color:#374151}
html[data-tema="grafito"] .plan-card{background:#fff;border-color:#D8DDE5}
html[data-tema="grafito"] .plan-card h3{color:#212529}
html[data-tema="grafito"] .plan-card .precio{color:#606C5D}
html[data-tema="grafito"] .pago-card{background:#fff;border-color:#D8DDE5}
html[data-tema="grafito"] .pago-card-title{color:#212529}
html[data-tema="grafito"] .horario-dia-nombre,html[data-tema="grafito"] .horario-col-header{color:#606C5D!important}
html[data-tema="grafito"] .theme-card-name{color:#212529!important}
html[data-tema="grafito"] .theme-card-desc{color:#6B7280!important}
html[data-tema="grafito"] .cd-label{color:rgba(43,48,58,0.6)!important}
html[data-tema="grafito"] *[style*="color:rgba(0,212,255"]{color:#606C5D!important}
html[data-tema="grafito"] *[style*="color:#00c8f0"]{color:#606C5D!important}
html[data-tema="grafito"] *[style*="color:rgba(255,255,255"]{color:rgba(43,48,58,.45)!important}
html[data-tema="grafito"] *[style*="color:#999"]{color:rgba(43,48,58,.45)!important}""",

    "calido": """html[data-tema="calido"] body{background:#FAF9F6;color:#1C1C1E}
html[data-tema="calido"] .topbar{background:#FFFFFF;border-bottom:1px solid #E5E5E7;box-shadow:none}
html[data-tema="calido"] .topbar-brand{color:#1C1C1E}
html[data-tema="calido"] .topbar-brand span{color:#706F6D}
html[data-tema="calido"] .user-name{color:#1C1C1E}
html[data-tema="calido"] .user-role{color:#7C7C80}
html[data-tema="calido"] .user-profile{border-color:#E5E5E7;background:#FAF9F6}
html[data-tema="calido"] .user-avatar{background:#F2F2F7;color:#48484A}
html[data-tema="calido"] .sidebar{background:#FFFFFF;border-right:1px solid #E5E5E7}
html[data-tema="calido"] .main-content{background:#FAF9F6}
html[data-tema="calido"] .sidebar-section-title{color:#AEAEB2}
html[data-tema="calido"] .nav-item{color:#7C7C80}
html[data-tema="calido"] .nav-item:hover{color:#1C1C1E;background:#FAF9F6;border-left-color:#D1D1D6}
html[data-tema="calido"] .nav-item.active{color:#1C1C1E;background:rgba(28,28,30,.05);border-left-color:#1C1C1E}
html[data-tema="calido"] .config-group-label{color:#1C1C1E}
html[data-tema="calido"] .config-group-arrow{color:#7C7C80}
html[data-tema="calido"] .sidebar-config-header{border-top-color:#E5E5E7}
html[data-tema="calido"] .sidebar-config-header:hover{background:#FAF9F6}
html[data-tema="calido"] .config-section-divider{background:#E5E5E7}
html[data-tema="calido"] .config-panel-title{color:#1C1C1E;font-weight:600}
html[data-tema="calido"] .config-panel-title span{color:#706F6D}
html[data-tema="calido"] .config-panel-subtitle{color:#7C7C80}
html[data-tema="calido"] .config-form-card{background:#FFFFFF;border-color:#E5E5E7;box-shadow:0 2px 8px rgba(0,0,0,.02);border-radius:10px}
html[data-tema="calido"] .config-form-card-title{color:#1C1C1E;border-bottom-color:#F2F2F7;font-weight:500}
html[data-tema="calido"] .form-group label{color:#2C2C2E;font-weight:500}
html[data-tema="calido"] .form-control{background:#FAF9F6;border-color:#D1D1D6;color:#1C1C1E;border-width:1px;border-radius:8px}
html[data-tema="calido"] .form-control:focus{border-color:#1C1C1E;background:#FFFFFF;box-shadow:0 0 0 3px rgba(28,28,30,.08)}
html[data-tema="calido"] .form-control::placeholder{color:#AEAEB2}
html[data-tema="calido"] select.form-control{background-color:#FAF9F6!important;color-scheme:light}
html[data-tema="calido"] select.form-control option{background:#FAF9F6;color:#1C1C1E}
html[data-tema="calido"] .custom-dropdown-btn{background:#FAF9F6;border-color:#D1D1D6;color:#1C1C1E;border-width:1px}
html[data-tema="calido"] .custom-dropdown-menu{background:#fff;border-color:#D1D1D6}
html[data-tema="calido"] .cd-item-text{color:#1C1C1E}
html[data-tema="calido"] .ptab{background:#FFFFFF;border-color:#E5E5E7;color:#7C7C80;border-width:1px;border-radius:8px}
html[data-tema="calido"] .ptab:hover{color:#1C1C1E;background:#FAF9F6}
html[data-tema="calido"] .ptab.active{background:#1C1C1E;border-color:#1C1C1E;color:white;box-shadow:none}
html[data-tema="calido"] .btn-primary{background:#1C1C1E;color:white;border-radius:8px}
html[data-tema="calido"] .btn-primary:hover{background:#2C2C2E;box-shadow:none;transform:translateY(-1px)}
html[data-tema="calido"] .btn-secondary{background:#FFFFFF;border-color:#E5E5E7;color:#48484A;border-width:1px;border-radius:8px}
html[data-tema="calido"] .btn-secondary:hover{background:#FAF9F6;border-color:#D1D1D6;color:#1C1C1E}
html[data-tema="calido"] .btn-icon-edit{background:rgba(28,28,30,.06);color:#1C1C1E}
html[data-tema="calido"] .data-table th{color:#2C2C2E;border-bottom-color:#E5E5E7}
html[data-tema="calido"] .data-table td{color:#3C3C3E;border-bottom-color:#F2F2F7}
html[data-tema="calido"] .data-table tr:hover td{background:rgba(28,28,30,.03)}
html[data-tema="calido"] .table-search{background:#fff;border-color:#E5E5E7;border-width:1px}
html[data-tema="calido"] .table-search input{color:#1C1C1E}
html[data-tema="calido"] .spinner{border-color:rgba(28,28,30,.15);border-top-color:#1C1C1E}
html[data-tema="calido"] .modal-box{background:#fff;border-color:#E5E5E7;color:#1C1C1E}
html[data-tema="calido"] .modal-title{color:#1C1C1E}
html[data-tema="calido"] .modal-confirmacion-dialog{background:#fff;border-color:#E5E5E7}
html[data-tema="calido"] .modal-confirmacion-title{color:#1C1C1E}
html[data-tema="calido"] .modal-confirmacion-message{color:#3C3C3E}
html[data-tema="calido"] .modal-confirmacion-btn{border-color:#E5E5E7;background:rgba(28,28,30,.05);color:#1C1C1E}
html[data-tema="calido"] .info-box{background:rgba(28,28,30,.04);border-color:rgba(28,28,30,.1);color:#48484A}
html[data-tema="calido"] .info-box strong{color:#1C1C1E}
html[data-tema="calido"] .modulo-check{background:#fff;border-color:#E5E5E7;border-width:1px}
html[data-tema="calido"] .modulo-check label{color:#1C1C1E}
html[data-tema="calido"] .modulo-check input[type="checkbox"]{accent-color:#1C1C1E}
html[data-tema="calido"] .plan-card{background:rgba(255,255,255,.85);border-color:#E5E5E7;border-width:1px}
html[data-tema="calido"] .plan-card h3{color:#1C1C1E}
html[data-tema="calido"] .plan-card .precio{color:#706F6D}
html[data-tema="calido"] .pago-card{background:rgba(255,255,255,.85);border-color:#E5E5E7;border-width:1px}
html[data-tema="calido"] .pago-card-title{color:#1C1C1E}
html[data-tema="calido"] .upload-zone{border-color:#D1D1D6}
html[data-tema="calido"] .horario-dia-nombre,html[data-tema="calido"] .horario-col-header{color:#1C1C1E!important}
html[data-tema="calido"] .theme-card-name{color:#1C1C1E!important}
html[data-tema="calido"] .theme-card-desc{color:#7C7C80!important}
html[data-tema="calido"] .cd-label{color:rgba(44,44,46,0.6)!important}
html[data-tema="calido"] *[style*="color:rgba(0,212,255"]{color:rgba(28,28,30,.55)!important}
html[data-tema="calido"] *[style*="color:#00c8f0"]{color:rgba(28,28,30,.55)!important}
html[data-tema="calido"] *[style*="color:rgba(255,255,255"]{color:rgba(28,28,30,.35)!important}
html[data-tema="calido"] *[style*="color:#999"]{color:rgba(28,28,30,.4)!important}""",

    "polar": """html[data-tema="polar"] body{background:#F4F6F8;color:#1E252B}
html[data-tema="polar"] .topbar{background:#FFFFFF;border-bottom:1px solid #E4E7EB;box-shadow:none}
html[data-tema="polar"] .topbar-brand{color:#1E252B}
html[data-tema="polar"] .topbar-brand span{color:#4A7B9D}
html[data-tema="polar"] .user-name{color:#1E252B}
html[data-tema="polar"] .user-role{color:#637381}
html[data-tema="polar"] .user-profile{border-color:#E4E7EB;background:#F4F6F8}
html[data-tema="polar"] .user-avatar{background:#FFFFFF;color:#4A7B9D}
html[data-tema="polar"] .sidebar{background:#FFFFFF;border-right:1px solid #E4E7EB}
html[data-tema="polar"] .main-content{background:#F4F6F8}
html[data-tema="polar"] .sidebar-section-title{color:#A8B3BC}
html[data-tema="polar"] .nav-item{color:#637381}
html[data-tema="polar"] .nav-item:hover{color:#1E252B;background:#F4F6F8;border-left-color:#CED4DA}
html[data-tema="polar"] .nav-item.active{color:#4A7B9D;background:rgba(74,123,157,.08);border-left-color:#4A7B9D;font-weight:600}
html[data-tema="polar"] .config-group-label{color:#1E252B}
html[data-tema="polar"] .config-group-arrow{color:#637381}
html[data-tema="polar"] .sidebar-config-header{border-top-color:#E4E7EB}
html[data-tema="polar"] .sidebar-config-header:hover{background:#F4F6F8}
html[data-tema="polar"] .config-section-divider{background:#E4E7EB}
html[data-tema="polar"] .config-panel-title{color:#1E252B}
html[data-tema="polar"] .config-panel-title span{color:#4A7B9D}
html[data-tema="polar"] .config-panel-subtitle{color:#637381}
html[data-tema="polar"] .config-form-card{background:#FFFFFF;border-color:#E4E7EB;box-shadow:0 4px 6px -1px rgba(0,0,0,.02)}
html[data-tema="polar"] .config-form-card-title{color:#1E252B;border-bottom-color:#E4E7EB}
html[data-tema="polar"] .form-group label{color:#4A7B9D}
html[data-tema="polar"] .form-control{background:#FFFFFF;border-color:#CED4DA;color:#1E252B;border-width:1px}
html[data-tema="polar"] .form-control:focus{border-color:#4A7B9D;background:#FFFFFF;box-shadow:0 0 0 3px rgba(74,123,157,.15)}
html[data-tema="polar"] .form-control::placeholder{color:#A8B3BC}
html[data-tema="polar"] select.form-control{background-color:#FFFFFF!important;color-scheme:light}
html[data-tema="polar"] .custom-dropdown-btn{background:#FFFFFF;border-color:#CED4DA;color:#1E252B;border-width:1px}
html[data-tema="polar"] .custom-dropdown-menu{background:#FFFFFF;border-color:#E4E7EB}
html[data-tema="polar"] .cd-item-text{color:#1E252B}
html[data-tema="polar"] .ptab{background:#FFFFFF;border-color:#E4E7EB;color:#637381;border-width:1px}
html[data-tema="polar"] .ptab:hover{color:#1E252B;background:#F4F6F8;border-color:#CED4DA}
html[data-tema="polar"] .ptab.active{background:#4A7B9D;border-color:#4A7B9D;color:white;box-shadow:none}
html[data-tema="polar"] .btn-primary{background:#4A7B9D;color:white}
html[data-tema="polar"] .btn-primary:hover{background:#3D6682;box-shadow:0 4px 12px rgba(74,123,157,.2)}
html[data-tema="polar"] .btn-secondary{background:#FFFFFF;border-color:#E4E7EB;color:#637381;border-width:1px}
html[data-tema="polar"] .btn-secondary:hover{background:#F4F6F8;border-color:#CED4DA;color:#1E252B}
html[data-tema="polar"] .data-table th{color:#4A7B9D;border-bottom-color:#E4E7EB}
html[data-tema="polar"] .data-table td{color:#454F5B;border-bottom-color:#E4E7EB}
html[data-tema="polar"] .data-table tr:hover td{background:#F4F6F8}
html[data-tema="polar"] .table-search{background:#FFFFFF;border-color:#E4E7EB;border-width:1px}
html[data-tema="polar"] .table-search input{color:#1E252B}
html[data-tema="polar"] .spinner{border-color:rgba(74,123,157,.2);border-top-color:#4A7B9D}
html[data-tema="polar"] .modal-overlay{background:rgba(30,37,43,.4)}
html[data-tema="polar"] .modal-box{background:#FFFFFF;border-color:#E4E7EB;color:#1E252B}
html[data-tema="polar"] .modal-title{color:#4A7B9D}
html[data-tema="polar"] .modal-confirmacion-dialog{background:#FFFFFF;border-color:#E4E7EB}
html[data-tema="polar"] .modal-confirmacion-title{color:#4A7B9D}
html[data-tema="polar"] .modal-confirmacion-message{color:#1E252B}
html[data-tema="polar"] .modal-confirmacion-btn{border-color:#E4E7EB;background:rgba(74,123,157,.08);color:#4A7B9D}
html[data-tema="polar"] .info-box{background:rgba(74,123,157,.07);border-color:rgba(74,123,157,.2);color:#454F5B}
html[data-tema="polar"] .info-box strong{color:#4A7B9D}
html[data-tema="polar"] .modulo-check{background:#FFFFFF;border-color:#E4E7EB;border-width:1px}
html[data-tema="polar"] .modulo-check label{color:#1E252B}
html[data-tema="polar"] .plan-card{background:#FFFFFF;border-color:#E4E7EB;border-width:1px}
html[data-tema="polar"] .plan-card h3{color:#1E252B}
html[data-tema="polar"] .plan-card .precio{color:#4A7B9D}
html[data-tema="polar"] .pago-card{background:#FFFFFF;border-color:#E4E7EB;border-width:1px}
html[data-tema="polar"] .pago-card-title{color:#1E252B}
html[data-tema="polar"] .upload-zone{border-color:#CED4DA}
html[data-tema="polar"] .horario-dia-nombre,html[data-tema="polar"] .horario-col-header{color:#4A7B9D!important}
html[data-tema="polar"] .theme-card-name{color:#1E252B!important}
html[data-tema="polar"] .theme-card-desc{color:#637381!important}
html[data-tema="polar"] .cd-label{color:rgba(74,123,157,0.7)!important}
html[data-tema="polar"] *[style*="color:rgba(0,212,255"]{color:#4A7B9D!important}
html[data-tema="polar"] *[style*="color:#00c8f0"]{color:#4A7B9D!important}
html[data-tema="polar"] *[style*="color:rgba(255,255,255"]{color:rgba(30,37,43,.38)!important}
html[data-tema="polar"] *[style*="color:#999"]{color:rgba(74,123,157,.45)!important}""",
}


# ── Datos completos de los 7 temas predeterminados ────────────────────────────

TEMAS_PREDETERMINADOS = [
    {
        "nombre":           "Nidus Azul",
        "clave":            "default",
        "descripcion":      "Azul marino · Corporativo",
        "orden":            1,
        "es_predeterminado": True,
        "activo":           True,
        "vista_previa": {
            "color_navegacion":  "#042243",
            "color_fondo":       "#EEF2FF",
            "color_acento":      "#00c8f0",
            "color_barra_fuerte": "rgba(4,34,67,0.3)",
            "color_barra_suave":  "rgba(4,34,67,0.15)",
            "borde_nav":         "",
            "borde_topbar":      "",
            "borde_swatch_nav":  "",
            "borde_swatch_fondo": "",
        },
        "colores_tarjeta": {
            "fondo":            "linear-gradient(135deg,#042243,#00c8f0)",
            "texto":            "#fff",
            "borde":            "rgba(0,200,240,.4)",
            "sombra":           "rgba(4,34,67,.3)",
            "texto_descripcion": "rgba(255,255,255,.75)",
        },
        "css": _CSS["default"],
    },
    {
        "nombre":           "Noche Cyan",
        "clave":            "oscuro-cyan",
        "descripcion":      "Oscuro profundo · Acento cyan",
        "orden":            2,
        "es_predeterminado": False,
        "activo":           True,
        "vista_previa": {
            "color_navegacion":  "#111827",
            "color_fondo":       "#0B0F17",
            "color_acento":      "#06B6D4",
            "color_barra_fuerte": "rgba(6,182,212,0.45)",
            "color_barra_suave":  "rgba(6,182,212,0.15)",
            "borde_nav":         "",
            "borde_topbar":      "",
            "borde_swatch_nav":  "",
            "borde_swatch_fondo": "",
        },
        "colores_tarjeta": {
            "fondo":            "linear-gradient(135deg,#06B6D4,#0284C7)",
            "texto":            "#0B0F17",
            "borde":            "rgba(6,182,212,.5)",
            "sombra":           "rgba(2,132,199,.3)",
            "texto_descripcion": "rgba(11,15,23,.65)",
        },
        "css": _CSS["oscuro-cyan"],
    },
    {
        "nombre":           "Bosque",
        "clave":            "bosque",
        "descripcion":      "Nav oscuro · Fondo claro · Oliva",
        "orden":            3,
        "es_predeterminado": False,
        "activo":           True,
        "vista_previa": {
            "color_navegacion":  "#111827",
            "color_fondo":       "#F3F4F6",
            "color_acento":      "#606C5D",
            "color_barra_fuerte": "rgba(96,108,93,0.45)",
            "color_barra_suave":  "rgba(96,108,93,0.18)",
            "borde_nav":         "",
            "borde_topbar":      "",
            "borde_swatch_nav":  "",
            "borde_swatch_fondo": "",
        },
        "colores_tarjeta": {
            "fondo":            "linear-gradient(135deg,#606C5D,#4A5548)",
            "texto":            "#fff",
            "borde":            "rgba(255,255,255,.3)",
            "sombra":           "rgba(74,85,72,.3)",
            "texto_descripcion": "rgba(255,255,255,.75)",
        },
        "css": _CSS["bosque"],
    },
    {
        "nombre":           "Galaxia",
        "clave":            "galaxia",
        "descripcion":      "Noche oscura · Rosa",
        "orden":            4,
        "es_predeterminado": False,
        "activo":           True,
        "vista_previa": {
            "color_navegacion":  "#0F1524",
            "color_fondo":       "#090D16",
            "color_acento":      "#FB7185",
            "color_barra_fuerte": "rgba(251,113,133,0.6)",
            "color_barra_suave":  "rgba(251,113,133,0.2)",
            "borde_nav":         "",
            "borde_topbar":      "",
            "borde_swatch_nav":  "",
            "borde_swatch_fondo": "",
        },
        "colores_tarjeta": {
            "fondo":            "linear-gradient(135deg,#FB7185,#E11D48)",
            "texto":            "#F5EFE9",
            "borde":            "rgba(251,113,133,.45)",
            "sombra":           "rgba(225,29,72,.25)",
            "texto_descripcion": "rgba(245,239,233,.8)",
        },
        "css": _CSS["galaxia"],
    },
    {
        "nombre":           "Grafito",
        "clave":            "grafito",
        "descripcion":      "Carbón · Claro / Verde musgo",
        "orden":            5,
        "es_predeterminado": False,
        "activo":           True,
        "vista_previa": {
            "color_navegacion":  "#212529",
            "color_fondo":       "#F1F3F5",
            "color_acento":      "#606C5D",
            "color_barra_fuerte": "rgba(96,108,93,0.45)",
            "color_barra_suave":  "rgba(96,108,93,0.18)",
            "borde_nav":         "",
            "borde_topbar":      "",
            "borde_swatch_nav":  "",
            "borde_swatch_fondo": "",
        },
        "colores_tarjeta": {
            "fondo":            "linear-gradient(135deg,#606C5D,#4A5548)",
            "texto":            "#fff",
            "borde":            "rgba(255,255,255,.3)",
            "sombra":           "rgba(74,85,72,.3)",
            "texto_descripcion": "rgba(255,255,255,.75)",
        },
        "css": _CSS["grafito"],
    },
    {
        "nombre":           "Cálido Claro",
        "clave":            "calido",
        "descripcion":      "Blanco puro · Minimalista",
        "orden":            6,
        "es_predeterminado": False,
        "activo":           True,
        "vista_previa": {
            "color_navegacion":  "#FFFFFF",
            "color_fondo":       "#FAF9F6",
            "color_acento":      "#1C1C1E",
            "color_barra_fuerte": "rgba(28,28,30,0.22)",
            "color_barra_suave":  "rgba(28,28,30,0.1)",
            "borde_nav":         "border-right:1px solid #E5E5E7;",
            "borde_topbar":      "border-bottom:1px solid #E5E5E7;",
            "borde_swatch_nav":  "border:1.5px solid #D1D1D6;",
            "borde_swatch_fondo": "border:1.5px solid #D1D1D6;",
        },
        "colores_tarjeta": {
            "fondo":            "#1C1C1E",
            "texto":            "#fff",
            "borde":            "rgba(255,255,255,.25)",
            "sombra":           "rgba(0,0,0,.25)",
            "texto_descripcion": "rgba(255,255,255,.75)",
        },
        "css": _CSS["calido"],
    },
    {
        "nombre":           "Polar",
        "clave":            "polar",
        "descripcion":      "Blanco limpio · Azul acero",
        "orden":            7,
        "es_predeterminado": False,
        "activo":           True,
        "vista_previa": {
            "color_navegacion":  "#FFFFFF",
            "color_fondo":       "#F4F6F8",
            "color_acento":      "#4A7B9D",
            "color_barra_fuerte": "rgba(74,123,157,0.5)",
            "color_barra_suave":  "rgba(74,123,157,0.18)",
            "borde_nav":         "border-right:1px solid #E4E7EB;",
            "borde_topbar":      "border-bottom:1px solid #E4E7EB;",
            "borde_swatch_nav":  "border:1.5px solid #E4E7EB;",
            "borde_swatch_fondo": "border:1.5px solid #E4E7EB;",
        },
        "colores_tarjeta": {
            "fondo":            "#4A7B9D",
            "texto":            "#fff",
            "borde":            "rgba(255,255,255,.3)",
            "sombra":           "rgba(74,123,157,.3)",
            "texto_descripcion": "rgba(255,255,255,.75)",
        },
        "css": _CSS["polar"],
    },
]


class AparienciaModel:

    @staticmethod
    def listar(solo_activos=True) -> list:
        filtro = {"activo": True} if solo_activos else {}
        return list(_col().find(filtro).sort("orden", 1))

    @staticmethod
    def obtener(apariencia_id: str):
        try:
            return _col().find_one({"_id": ObjectId(apariencia_id)})
        except Exception:
            return None

    @staticmethod
    def buscar_por_clave(clave: str):
        return _col().find_one({"clave": clave.strip()})

    @staticmethod
    def crear(datos: dict) -> str:
        doc = {
            "nombre":           datos.get("nombre", "").strip(),
            "clave":            datos.get("clave", "").strip(),
            "descripcion":      datos.get("descripcion", "").strip(),
            "orden":            int(datos.get("orden", 99)),
            "es_predeterminado": bool(datos.get("es_predeterminado", False)),
            "activo":           bool(datos.get("activo", True)),
            "vista_previa":     datos.get("vista_previa", {}),
            "colores_tarjeta":  datos.get("colores_tarjeta", {}),
            "css":              datos.get("css", ""),
            "creado_en":        datetime.utcnow(),
            "actualizado_en":   None,
        }
        return str(_col().insert_one(doc).inserted_id)

    @staticmethod
    def actualizar(apariencia_id: str, datos: dict):
        campos = {}
        for k in ("nombre", "descripcion", "orden", "activo",
                  "vista_previa", "colores_tarjeta", "css"):
            if k in datos:
                campos[k] = datos[k]
        campos["actualizado_en"] = datetime.utcnow()
        _col().update_one({"_id": ObjectId(apariencia_id)}, {"$set": campos})

    @staticmethod
    def eliminar(apariencia_id: str):
        _col().delete_one({"_id": ObjectId(apariencia_id)})

    @staticmethod
    def sembrar_predeterminados() -> int:
        """Inserta los 7 temas base si la colección está vacía. Idempotente."""
        if _col().count_documents({}) > 0:
            return 0
        _col().insert_many([
            {**t, "creado_en": datetime.utcnow(), "actualizado_en": None}
            for t in TEMAS_PREDETERMINADOS
        ])
        return len(TEMAS_PREDETERMINADOS)
