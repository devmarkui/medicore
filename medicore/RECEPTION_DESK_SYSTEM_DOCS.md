# HIMS-Style Dynamic Reception Desk System

## 📋 Overview

A complete clinic reception system with dynamic service management, real-time bill calculations, and professional HIMS-style UI. Everything is driven from the database—no hardcoded services or categories.

---

## 🗄️ DATABASE SCHEMA

### Tables Created

#### 1. `service_categories`
Manages service groups/tabs that appear on the reception desk.

```sql
- category_id (PK, AUTO_INCREMENT)
- category_name (UNIQUE, VARCHAR 120)
- icon_class (VARCHAR 60) - e.g., "icon-stethoscope"
- display_order (INT) - Controls tab order
- is_active (BOOLEAN) - Active/Inactive status
- description (TEXT)
- created_at / updated_at (TIMESTAMPS)
```

**Default Categories:**
- All Services (always first, shows all items)
- OPD Consultation
- Laboratory
- Imaging
- Pharmacy
- Procedures

#### 2. `service_items`
Individual services/products that can be added to bills.

```sql
- item_id (PK, AUTO_INCREMENT)
- item_code (UNIQUE, VARCHAR 64) - e.g., "OPD001"
- item_name (VARCHAR 200)
- category_id (FK → service_categories)
- price (DECIMAL 12,2)
- description (TEXT)
- is_active (BOOLEAN)
- display_order (INT)
- created_at / updated_at (TIMESTAMPS)
```

**Sample Items:**
- General Consultation: Rs. 500
- Blood Test - CBC: Rs. 450
- X-Ray - Chest: Rs. 800
- And more...

---

## 🧭 BACKEND ROUTES

### Settings Routes (Service Management)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/settings/services` | GET | Dashboard to manage categories and items |
| `/settings/services/category/add` | POST | Add new service category |
| `/settings/services/category/edit/<id>` | POST | Edit category details |
| `/settings/services/category/toggle/<id>` | POST | Activate/deactivate category |
| `/settings/services/item/add` | POST | Add new service item |
| `/settings/services/item/edit/<id>` | POST | Edit item details |
| `/settings/services/item/toggle/<id>` | POST | Activate/deactivate item |

### API Routes (Reception Desk)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/appointments/api/services/categories` | GET | Fetch all active categories (JSON) |
| `/appointments/api/services/items/<category_id>` | GET | Fetch items for a category (JSON) |
| `/appointments/api/services/all` | GET | Fetch all items from all categories (JSON) |
| `/appointments/reception-desk` | GET | Modern HIMS-style reception desk page |

---

## 🎨 FRONTEND - RECEPTION DESK (reception_desk_v2.html)

### Layout (NO VERTICAL SCROLL)

```
┌────────────────────────────────────────────────────────────┐
│ PATIENT REGISTRATION (Full Width)                          │
│ Phone | Name | Gender | Age | NIC | [Search/Add Button]   │
└────────────────────────────────────────────────────────────┘
┌──────────────────────────────┬──────────────────────────────┐
│   SERVICES (70%)              │   BILL SUMMARY (30%)         │
│ ┌──────────────────────────┐  │ ┌──────────────────────────┐ │
│ │ [All] [OPD] [Lab] [..] │  │ │ Selected Items List       │ │
│ ├──────────────────────────┤  │ ├──────────────────────────┤ │
│ │ Search: ________________  │  │ Item 1     Qty:1-  +  Line│ │
│ ├──────────────────────────┤  │ │                    Total  │ │
│ │ [Service Cards Grid]     │  │ │                          │ │
│ │ ┌─────┐ ┌─────┐ ┌─────┐ │  │ ├──────────────────────────┤ │
│ │ │OPD  │ │ Lab │ │Pharm│ │  │ │ Subtotal:  Rs. 0000.00   │ │
│ │ │Rs.  │ │ Rs. │ │ Rs. │ │  │ │ Discount:  Rs. [____]    │ │
│ │ └─────┘ └─────┘ └─────┘ │  │ │ Grand Total: Rs. 0000.00 │ │
│ │                          │  │ ├──────────────────────────┤ │
│ │ (Click to add to bill)   │  │ │ Remarks: ____________    │ │
│ └──────────────────────────┘  │ │ Payment:  [Select ___]   │ │
│                                │ │ [Clear] [Confirm]        │ │
│                                │ └──────────────────────────┘ │
└──────────────────────────────┴──────────────────────────────┘
```

### Key Features

1. **Patient Registration (Top)**
   - Phone lookup for existing patients
   - Auto-fill patient details if found
   - Quick entry for new patients
   - Fields: Phone, Name, Gender, Age, NIC

2. **Dynamic Service Tabs**
   - All categories loaded from database
   - "All Services" shows everything
   - Category tabs show filtered items
   - Order controlled by `display_order` field

3. **Service Item Cards**
   - Grid layout (3 columns)
   - Click to add to bill
   - Shows: Name, Code, Price
   - Searchable by name/code

4. **Bill Summary Panel (Sticky)**
   - Real-time item list with qty controls
   - Line total calculations
   - Subtotal + Discount = Grand Total
   - Payment method selector
   - Remarks field for special notes

5. **Dynamic Updates**
   - Qty +/- instantly recalculates totals
   - Remove item button
   - Clear bill to start over
   - All calculations in real-time

### Frontend Logic (JavaScript)

```javascript
// Load services on page load
loadServices() → fetches categories + all items from API

// Render tabs
renderTabs() → creates buttons from category data

// Show category
showCategory(id) → filters and displays items for that category

// Add item to bill
addItemToBill(item) → adds/increments in selectedItems array

// Render bill
renderBillItems() → creates bill rows with qty controls

// Calculate totals
updateTotals() → subtotal - discount = grand total
```

---

## ⚙️ SETTINGS PAGE (services_management.html)

### Tab 1: Service Categories

**Add New Category:**
- Category Name (required)
- Icon Class (optional, e.g., "icon-stethoscope")
- Description
- Auto-assigned next display_order

**Manage Existing:**
- Table showing all categories
- Edit button → modal/inline edit
- Activate/Deactivate toggle
- Display order for sequencing

### Tab 2: Service Items

**Add New Item:**
- Item Code (required, unique)
- Item Name (required)
- Category selector (FK)
- Price (Rs.)
- Description (optional)
- Auto-assigned next display_order

**Manage Existing:**
- Table showing all items
- Filter by category
- Edit button → modal/inline edit
- Activate/Deactivate toggle
- Price updates instantly

---

## 🔄 DYNAMIC SYSTEM BEHAVIOR

### When Admin Adds a New Category in Settings

1. **Database:** New row inserted into `service_categories`
2. **Reception Desk:** Next time user refreshes OR fetches `/api/services/categories`, new tab appears
3. **Display:** Positioned based on `display_order`
4. **Status:** Only active (`is_active = 1`) categories shown

### When Admin Adds a New Item in Settings

1. **Database:** New row inserted into `service_items`
2. **Assigned to Category:** Via `category_id` FK
3. **Reception Desk:** Next API fetch returns item in correct category tab
4. **Price:** Auto-used in bill calculations
5. **Status:** Only active (`is_active = 1`) items shown

### When Admin Deactivates a Category

1. **Reception Desk:** Tab disappears
2. **All Services Tab:** Items from that category hidden
3. **Existing Bills:** No new items can be added (previously added stay)

### When Admin Deactivates an Item

1. **Reception Desk:** Item card hidden from all tabs
2. **All Services:** Item disappears
3. **New Bills:** Cannot be selected
4. **Existing Bills:** Already-selected items remain (quantity adjustable)

---

## 💡 USE CASE FLOW

### Receptionist Workflow

```
1. Open Reception Desk (/appointments/reception-desk)
   ↓
2. Enter/Search patient by phone
   → If found: auto-populate details
   → If new: fill manually (Name, Gender, Age, NIC)
   ↓
3. Browse service tabs (OPD, Lab, Imaging, etc.)
   → All Services tab shows everything
   → Category tabs show filtered items
   ↓
4. Click service items to add
   → Item added to bill summary
   ↓
5. Adjust quantities using +/- buttons
   → Bill updates instantly
   ↓
6. (Optional) Apply discount
   → Grand total recalculates
   ↓
7. Select payment method (Cash / Card)
   ↓
8. Click Confirm
   → Invoice created
   → Payment recorded
   → Bill cleared for next patient
```

### Admin Workflow (Add New Service Category)

```
1. Open Settings → Services Management
   ↓
2. Click "Service Categories" tab
   ↓
3. Fill "Add New Category" form
   - Name: "Dental Services"
   - Icon: "icon-teeth"
   - Description: "Dental examinations and treatments"
   ↓
4. Submit
   ↓
5. New tab appears on Reception Desk immediately (after refresh)
```

### Admin Workflow (Add New Service Item)

```
1. Open Settings → Services Management
   ↓
2. Click "Service Items" tab
   ↓
3. Fill "Add New Item" form
   - Code: "DENT001"
   - Name: "Dental Checkup"
   - Category: "Dental Services" (select from dropdown)
   - Price: "800" (Rs.)
   - Description: "Routine dental examination"
   ↓
4. Submit
   ↓
5. Item appears under "Dental Services" tab on Reception Desk
```

---

## 📱 RESPONSIVE BEHAVIOR

- **Desktop-first** design
- Tabs scroll horizontally if many categories
- Service grid is responsive (3 columns → 2 → 1 on smaller screens)
- Bill panel stays 30% width unless mobile

---

## 🔒 SECURITY

- CSRF token validation on all forms
- Role-based access: `ALLOWED_ROLES = ["SuperAdmin", "CenterAdmin"]` for settings
- Role-based access: `RECEPTION_ROLES` for reception desk
- All data validated before DB insert

---

## 📊 PERFORMANCE NOTES

- Categories/items cached on first load (can add refresh button if needed)
- API endpoints lightweight (simple SELECT queries)
- Bill calculations done on client-side (no server round-trips)
- Searching/filtering done on client-side JavaScript

---

## 🚀 HOW TO USE

### 1. Access Reception Desk

```
http://127.0.0.1:5001/appointments/reception-desk
```

### 2. Access Settings

```
http://127.0.0.1:5001/settings/services
```

### 3. Add Your First Category (Example)

1. Go to Settings → Services Management
2. Under "Service Categories" tab, fill form:
   - Name: "Emergency Services"
   - Icon: "icon-alert"
   - Description: "24/7 emergency care"
3. Click "Add Category"
4. New tab appears on Reception Desk

### 4. Add First Item

1. Under "Service Items" tab, fill form:
   - Code: "EMRG001"
   - Name: "Emergency Consultation"
   - Category: "Emergency Services"
   - Price: "2000"
2. Click "Add Item"
3. Item appears on Reception Desk under "Emergency Services" tab

---

## 🎯 TODO / ENHANCEMENTS (For Future)

- [ ] Patient registration: save to `patients` table on confirm
- [ ] Invoice creation: generate invoice from bill + services
- [ ] Payment processing: record in `payments` table
- [ ] Reorder categories/items (drag-drop)
- [ ] Bulk import services from CSV
- [ ] Service templates (predefined bundles)
- [ ] Discount rules (% or fixed)
- [ ] Service availability by time/day
- [ ] Receptionist performance metrics

---

## ✅ WHAT'S WORKING

✅ Database schema with categories and items  
✅ Settings management for categories and items  
✅ API endpoints for dynamic data loading  
✅ Modern HIMS-style reception page  
✅ Real-time bill calculations  
✅ Dynamic tabs from database  
✅ Search functionality  
✅ Qty adjustments  
✅ Discount calculations  
✅ Payment method selection  
✅ No hardcoded data  

---

## 📝 FILES CREATED/MODIFIED

| File | Change |
|------|--------|
| `sql/service_management.sql` | New schema |
| `medicore/routes/settings_routes.py` | Added 7 service management routes |
| `medicore/routes/appointment_routes.py` | Added 4 API endpoints + reception desk route |
| `medicore/templates/appointments/reception_desk_v2.html` | New modern UI |
| `medicore/templates/settings/services_management.html` | New settings page |

---

Generated: April 6, 2026
