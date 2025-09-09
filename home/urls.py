from django.urls import path
from . import views

urlpatterns = [
   path('',views.home,name='home'),
   path('custom/admin/',views.dashboard,name='dashboard'),
   path('custom/admin/download/sales/report/', views.download_sales_report_pdf, name='download_sales_report_pdf'),
   path('custom/admin/sales/chart/data/', views.sales_chart_data, name='sales_chart_data'),

]
