#!/bin/bash
# Quick Start Guide - HIMS-Style Reception Desk System

echo "🎯 HIMS-STYLE RECEPTION DESK SYSTEM - QUICK START"
echo "=================================================="
echo ""

# Check if Flask is running
echo "✓ Checking Flask server..."
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "  ✓ Flask is already running on http://127.0.0.1:5001"
else
    echo "  Starting Flask server..."
    cd /Users/aadhilaadhil/Downloads/Clinic/medicore
    /Users/aadhilaadhil/Downloads/Clinic/.venv/bin/python app.py > /dev/null 2>&1 &
    sleep 2
    echo "  ✓ Flask started on http://127.0.0.1:5001"
fi

echo ""
echo "📋 QUICK START STEPS:"
echo "==================="
echo ""

echo "1️⃣  LOGIN TO CLINIC"
echo "   URL: http://127.0.0.1:5001"
echo "   Username: admin@medicore.local"
echo "   Password: (check database admin user password)"
echo ""

echo "2️⃣  ADD A NEW SERVICE CATEGORY (Optional)"
echo "   Go to: Settings → Services Management"
echo "   Click: Service Categories tab"
echo "   Add:   "
echo "     - Name: \"Dental Services\""
echo "     - Icon: \"icon-teeth\""
echo "     - Description: \"Dental care and procedures\""
echo "   Submit"
echo ""

echo "3️⃣  ADD A NEW SERVICE ITEM (Optional)"
echo "   Go to: Settings → Services Management"
echo "   Click: Service Items tab"
echo "   Add:   "
echo "     - Code: \"DENT001\""
echo "     - Name: \"Dental Checkup\""
echo "     - Category: \"Dental Services\""
echo "     - Price: \"800\""
echo "   Submit"
echo ""

echo "4️⃣  TEST RECEPTION DESK"
echo "   Go to: Appointments → Reception Desk"
echo "   OR direct: http://127.0.0.1:5001/appointments/reception-desk"
echo ""

echo "5️⃣  TRY IT OUT"
echo "   a) Enter patient phone: 0701234567"
echo "   b) Fill patient details (Name, Gender, Age)"
echo "   c) Click tabs to see different service categories"
echo "   d) Click service items to add them to bill"
echo "   e) Use +/- to adjust quantities"
echo "   f) See bill update instantly"
echo "   g) Enter discount amount (optional)"
echo "   h) Select payment method"
echo "   i) Click Confirm"
echo ""

echo "🎨 KEY PAGES:"
echo "============="
echo "✓ Reception Desk (Modern UI):  /appointments/reception-desk"
echo "✓ Settings - Services:         /settings/services"
echo ""

echo "🔗 API ENDPOINTS (For Developers):"
echo "=================================="
echo "✓ Get all categories:     GET /appointments/api/services/categories"
echo "✓ Get items by category:  GET /appointments/api/services/items/<category_id>"
echo "✓ Get all items:          GET /appointments/api/services/all"
echo ""

echo "📊 DATABASE INFO:"
echo "================"
echo "Tables Created:"
echo "  ✓ service_categories (6 default categories)"
echo "  ✓ service_items (15 default items)"
echo ""

echo "✅ EVERYTHING IS READY!"
echo "====================="
echo ""
echo "💡 TIPS:"
echo "   • Add more categories in Settings to create new tabs"
echo "   • Prices update instantly in the reception bill"
echo "   • Deactivate categories/items to hide them (don't delete)"
echo "   • All data is dynamic - no hardcoding!"
echo ""
