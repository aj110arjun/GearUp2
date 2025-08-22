from django.urls import path
from . import views

urlpatterns = [
   path('',views.home,name='home'),
   path('custom/admin/',views.dashboard,name='dashboard'),
   path('admin/download-sales-report-pdf/', views.download_sales_report_pdf, name='download_sales_report_pdf'),

]
