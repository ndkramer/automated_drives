# AI Training Workflow for Field Variations

## 🎯 **The Problem You Identified**
Different vendors use different field labels:
- **Delivery Date** could be: "Promised Date", "Delivery On", "Ship By", "Due Date"
- **PO Number** could be: "Order No", "PO#", "Purchase Order #"
- **Vendor** could be: "Supplier", "From", "Company"

## 🚀 **Your Complete Training Solution**

### **1. Training Infrastructure (✅ Already Set Up)**
- **`ai_training_feedback`** table - Stores human corrections
- **`field_label_patterns`** table - Learns field name variations
- **`AdaptiveAIExtractionService`** - Uses learned patterns automatically

### **2. Three Ways to Train the AI**

#### **Method A: Reactive Training (When You Find Errors)**
```python
from services.adaptive_ai_service import AdaptiveAIExtractionService

service = AdaptiveAIExtractionService()

# Example: PDF used "Promised Date" instead of "Delivery Date"
service.add_training_feedback(
    pdf_upload_id=7,                    # Which document
    field_name='delivery_date',         # Standard field name  
    ai_value='2024-02-15',             # What AI extracted
    human_value='2024-02-15',          # Correct value (if AI was right)
    field_label_found='Promised Date',  # Label actually used in PDF
    feedback_type='confirmation'        # 'correction' or 'confirmation'
)
```

#### **Method B: Proactive Training (Before Problems)**
```python
# Teach common variations upfront
variations = [
    ('delivery_date', 'Promised Date'),
    ('delivery_date', 'Ship By'),
    ('delivery_date', 'Due On'),
    ('po_number', 'Order No'),
    ('po_number', 'PO#'),
    ('vendor_name', 'Supplier'),
    ('vendor_name', 'Sold By')
]

for field, variation in variations:
    # Add pattern without specific document
    service.add_training_feedback(
        pdf_upload_id=1,  # Use any valid ID
        field_name=field,
        ai_value=None,
        human_value=None,
        field_label_found=variation,
        feedback_type='new_pattern'
    )
```

#### **Method C: Automated Discovery (Run Periodically)**
```python
# Run this weekly to find missed patterns
python ai_training_strategies.py

# This will:
# 1. Analyze failed extractions
# 2. Suggest new patterns to add
# 3. Generate training datasets
```

### **3. Real-World Training Scenarios**

#### **Scenario 1: New Vendor Format**
You upload a PDF from "ACME Corp" and notice they use "Ship Date" instead of "Delivery Date":

```bash
# Step 1: Upload PDF (normal process)
curl -X POST -F "pdf_file=@acme_po.pdf" http://localhost:8080/upload

# Step 2: Check extraction results
python business_field_queries.py

# Step 3: If delivery_date is NULL but you see "Ship Date" in PDF
python -c "
from services.adaptive_ai_service import AdaptiveAIExtractionService
service = AdaptiveAIExtractionService()
service.add_training_feedback(8, 'delivery_date', None, '2024-03-15', 'Ship Date', 'new_pattern')
print('✅ AI learned: Ship Date = delivery_date')
"

# Step 4: Next ACME PDF will extract Ship Date correctly!
```

#### **Scenario 2: Mass Training from Discovery**
```bash
# Find all missed patterns
python ai_training_strategies.py

# Output might show:
# "Potential missed patterns:"
# "• delivery_date: 'due on'"
# "• po_number: 'order ref'"

# Add these patterns:
python -c "
from services.adaptive_ai_service import AdaptiveAIExtractionService
service = AdaptiveAIExtractionService()
service.add_training_feedback(1, 'delivery_date', None, None, 'due on', 'new_pattern')
service.add_training_feedback(1, 'po_number', None, None, 'order ref', 'new_pattern')
print('✅ Added new patterns')
"
```

### **4. Monitoring Training Progress**

#### **Check Current Patterns**
```python
# See what AI has learned
from services.adaptive_ai_service import AdaptiveAIExtractionService
service = AdaptiveAIExtractionService()
patterns = service.get_learned_patterns()

for field, variations in patterns.items():
    print(f"{field}: {[v[0] for v in variations]}")
    
# Output:
# delivery_date: ['Delivery Date', 'Promised Date', 'Ship Date', 'Due Date']
# po_number: ['PO Number', 'Purchase Order', 'Order Number', 'PO#']
```

#### **Track Performance**
```bash
# Monitor field-level accuracy
python ai_training_insights.py

# Shows which fields need improvement:
# "Contact Email: 66.7% 🔴 Needs Work"
# "PO Number: 100.0% 🟢 Excellent"
```

### **5. How The Learning Works**

#### **Before Training:**
```
AI Prompt: "Look for: Delivery Date, Due Date, Ship Date"
PDF contains: "Promised Date: 2024-02-15"
AI Result: ❌ delivery_date = null (missed it!)
```

#### **After Training:**
```
AI Prompt: "Look for: Delivery Date, Due Date, Ship Date, Promised Date"
PDF contains: "Promised Date: 2024-02-15"  
AI Result: ✅ delivery_date = "2024-02-15" (found it!)
```

### **6. Advanced Training Features**

#### **Pattern Confidence Scoring**
- **New patterns start at 0.7 confidence**
- **Successful extractions increase confidence**
- **Failed extractions decrease confidence**
- **High-confidence patterns appear first in AI prompts**

#### **Automatic Pattern Updates**
- **Usage tracking**: Counts how often each pattern is seen
- **Recency tracking**: When pattern was last encountered
- **Active/inactive**: Disable patterns that consistently fail

#### **Training Dataset Generation**
```bash
# Create training dataset for fine-tuning
python ai_training_strategies.py

# Generates: training_dataset_20250707_162740.json
# Contains: Input PDF text + Expected output fields
# Use for: Fine-tuning custom AI models
```

## 🎯 **Practical Training Schedule**

### **Week 1: Initial Setup**
- ✅ Already done - training tables created
- ✅ Add common field variations proactively
- ✅ Monitor initial accuracy with `ai_training_insights.py`

### **Ongoing: Reactive Training**
- 📊 **Daily**: Check `business_field_queries.py` for NULL fields
- 🔍 **Weekly**: Run `ai_training_strategies.py` for pattern discovery
- 📝 **Monthly**: Review and add feedback for consistently missed patterns

### **Example Training Commands**
```bash
# Add a new delivery date variation
python -c "
from services.adaptive_ai_service import AdaptiveAIExtractionService
service = AdaptiveAIExtractionService()
service.add_training_feedback(1, 'delivery_date', None, None, 'Target Delivery', 'new_pattern')
"

# Add a new PO number variation  
python -c "
from services.adaptive_ai_service import AdaptiveAIExtractionService
service = AdaptiveAIExtractionService()
service.add_training_feedback(1, 'po_number', None, None, 'Work Order', 'new_pattern')
"

# Add a new vendor variation
python -c "
from services.adaptive_ai_service import AdaptiveAIExtractionService
service = AdaptiveAIExtractionService()
service.add_training_feedback(1, 'vendor_name', None, None, 'Bill To', 'new_pattern')
"
```

## 💡 **Key Benefits**

✅ **Self-Improving**: AI gets better with every correction  
✅ **Vendor-Agnostic**: Adapts to any company's terminology  
✅ **Zero Downtime**: Learning happens without stopping the system  
✅ **Trackable**: See exactly what AI has learned and performance trends  
✅ **Scalable**: Works whether you have 10 or 10,000 different vendors  

## 🚀 **Next Steps**

1. **Start training on existing documents** where fields are NULL
2. **Add common variations proactively** based on your industry knowledge
3. **Set up weekly pattern discovery** to catch new variations automatically
4. **Monitor performance** and focus training on lowest-accuracy fields

**Your AI will become increasingly accurate and adaptable to any vendor format!** 🎉 