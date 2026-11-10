from pathlib import Path
import re

root = Path("inventra/app/src/main/java/com/inventra/app")

repo = root / "data/repository/InventraRepository.kt"
s = repo.read_text()
s = s.replace("import com.inventra.app.data.local.dao.CategoryDao", "import androidx.room.withTransaction\nimport com.inventra.app.data.local.InventraDatabase\nimport com.inventra.app.data.local.dao.CategoryDao")
s = s.replace("    private val saleDao: SaleDao\n)", "    private val saleDao: SaleDao,\n    private val database: InventraDatabase\n)")
a = s.index("    suspend fun addStockPurchase(purchase: StockPurchaseEntity) {")
b = s.index("\n    fun computeNewAvgCost", a)
s = s[:a] + """    suspend fun addStockPurchase(purchase: StockPurchaseEntity): Result<Unit> {
        if (!purchase.quantity.isFinite() || purchase.quantity <= 0.0)
            return Result.failure(IllegalArgumentException("الكمية يجب أن تكون أكبر من صفر"))
        if (!purchase.costPerUnit.isFinite() || purchase.costPerUnit < 0.0)
            return Result.failure(IllegalArgumentException("سعر التكلفة غير صالح"))
        return database.withTransaction {
            val product = productDao.getProductById(purchase.productId)
                ?: return@withTransaction Result.failure(IllegalArgumentException("المادة غير موجودة"))
            val existingValue = product.currentStockQty * product.currentAvgCost
            val newQty = product.currentStockQty + purchase.quantity
            val newAvgCost = (existingValue + purchase.quantity * purchase.costPerUnit) / newQty
            productDao.updateStockStats(purchase.productId, newQty, newAvgCost)
            stockPurchaseDao.insertPurchase(purchase)
            Result.success(Unit)
        }
    }
""" + s[b:]
a = s.index("    suspend fun addSale(")
b = s.index("\n    suspend fun deleteSale", a)
s = s[:a] + """    suspend fun addSale(
        productId: String,
        quantity: Double,
        sellingPricePerUnit: Double,
        date: Long,
        notes: String
    ): Result<Unit> {
        if (!quantity.isFinite() || quantity <= 0.0)
            return Result.failure(IllegalArgumentException("الكمية يجب أن تكون أكبر من صفر"))
        if (!sellingPricePerUnit.isFinite() || sellingPricePerUnit < 0.0)
            return Result.failure(IllegalArgumentException("سعر البيع غير صالح"))
        return database.withTransaction {
            val product = productDao.getProductById(productId)
                ?: return@withTransaction Result.failure(IllegalArgumentException("المادة غير موجودة"))
            if (product.currentStockQty < quantity)
                return@withTransaction Result.failure(IllegalArgumentException("الكمية المتوفرة غير كافية: ${product.currentStockQty}"))
            val totalRevenue = quantity * sellingPricePerUnit
            val avgCost = product.currentAvgCost
            val totalCost = quantity * avgCost
            val profit = totalRevenue - totalCost
            saleDao.insertSale(
                SaleEntity(
                    productId = productId,
                    quantity = quantity,
                    sellingPricePerUnit = sellingPricePerUnit,
                    totalRevenue = totalRevenue,
                    avgCostAtSale = avgCost,
                    totalCost = totalCost,
                    profit = profit,
                    date = date,
                    notes = notes
                )
            )
            productDao.updateStockStats(productId, product.currentStockQty - quantity, avgCost)
            Result.success(Unit)
        }
    }
""" + s[b:]
repo.write_text(s)

vm = root / "presentation/stock/StockViewModel.kt"
s = vm.read_text()
s = s.replace('''            repository.addStockPurchase(
                StockPurchaseEntity(
                    productId = productId, quantity = quantity, costPerUnit = costPerUnit,
                    totalCost = quantity * costPerUnit, date = date, supplier = supplier, notes = notes
                )
            )
            _result.value = StockInResult.Success''', '''            if (!costPerUnit.isFinite() || costPerUnit < 0) {
                _result.value = StockInResult.Error("سعر التكلفة غير صالح")
                return@launch
            }
            val outcome = repository.addStockPurchase(
                StockPurchaseEntity(
                    productId = productId, quantity = quantity, costPerUnit = costPerUnit,
                    totalCost = quantity * costPerUnit, date = date, supplier = supplier, notes = notes
                )
            )
            _result.value = outcome.fold(
                onSuccess = { StockInResult.Success },
                onFailure = { StockInResult.Error(it.message ?: "حدث خطأ غير معروف") }
            )''')
vm.write_text(s)

sales = root / "presentation/sales/SalesViewModel.kt"
s = sales.read_text()
s = s.replace('''            if (quantity <= 0) { _result.value = AddSaleResult.Error("Quantity must be > 0"); return@launch }
            if (sellingPrice < 0) { _result.value = AddSaleResult.Error("Selling price cannot be negative"); return@launch }''', '''            if (!quantity.isFinite() || quantity <= 0) { _result.value = AddSaleResult.Error("الكمية يجب أن تكون أكبر من صفر"); return@launch }
            if (!sellingPrice.isFinite() || sellingPrice < 0) { _result.value = AddSaleResult.Error("سعر البيع غير صالح"); return@launch }''')
sales.write_text(s)

strings = Path("inventra/app/src/main/res/values/strings.xml")
if strings.exists():
    t = strings.read_text()
    t = re.sub(r'(<string name="app_name">).*?(</string>)', r'\1محاسبة متجري\2', t)
    strings.write_text(t)

activity = root / "MainActivity.kt"
t = activity.read_text()
if "override fun attachBaseContext" not in t:
    t = t.replace("import android.os.Bundle", "import android.os.Bundle\nimport android.content.Context\nimport android.content.res.Configuration\nimport java.util.Locale")
    t = t.replace("class MainActivity : ComponentActivity() {", """class MainActivity : ComponentActivity() {
    override fun attachBaseContext(newBase: Context) {
        val locale = Locale("ar")
        Locale.setDefault(locale)
        val config = Configuration(newBase.resources.configuration)
        config.setLocale(locale)
        config.setLayoutDirection(locale)
        super.attachBaseContext(newBase.createConfigurationContext(config))
    }
""")
    activity.write_text(t)

translations = {
    '"Home"':'"الرئيسية"', '"Products"':'"المواد"', '"Analytics"':'"التقارير"',
    '"Inventory"':'"المخزون"', '"Add Product"':'"إضافة مادة"', '"Edit Product"':'"تعديل مادة"',
    '"Add Sale"':'"تسجيل مبيع"', '"Record Sale"':'"حفظ المبيع"', '"Stock In"':'"إدخال بضاعة"',
    '"Today"':'"اليوم"', '"Revenue"':'"إجمالي المبيعات"', '"Profit"':'"الربح"',
    '"Units Sold"':'"الكمية المباعة"', '"Recent Sales"':'"آخر المبيعات"',
    '"Low Stock Alerts"':'"تنبيهات نقص المخزون"', '"No sales yet"':'"لا توجد مبيعات بعد"',
    '"Product *"':'"المادة *"', '"Quantity *"':'"الكمية *"',
    '"Selling Price per Unit *"':'"سعر بيع القطعة *"', '"Notes (optional)"':'"ملاحظات (اختياري)"',
    '"Available"':'"المتوفر"', '"Avg Cost"':'"متوسط التكلفة"',
    '"Sale Preview"':'"ملخص المبيع"', '"Total Revenue"':'"إجمالي المبيع"',
    '"Total Cost (WAC)"':'"إجمالي التكلفة"', '"Margin"':'"هامش الربح"',
    '"Share Report"':'"مشاركة تقرير"', '"No inventory yet"':'"المخزون فارغ"',
    '"Add products and stock to see your inventory"':'"أضف المواد والبضاعة لعرض المخزون"',
    '"Name *"':'"اسم المادة *"', '"Category"':'"التصنيف"',
    '"Product Code"':'"رمز المادة"', '"Unit"':'"وحدة القياس"',
    '"Save Changes"':'"حفظ التعديلات"'
}
for file in root.rglob("*.kt"):
    body = file.read_text()
    for old_text, new_text in translations.items():
        body = body.replace(old_text, new_text)
    file.write_text(body)


dbmodule = Path("inventra/app/src/main/java/com/inventra/app/di/DatabaseModule.kt")
d = dbmodule.read_text()
d = d.replace("saleDao: SaleDao", """saleDao: SaleDao,
        database: InventraDatabase""")
d = d.replace("InventraRepository(productDao, categoryDao, stockPurchaseDao, saleDao)", "InventraRepository(productDao, categoryDao, stockPurchaseDao, saleDao, database)")
if "database: InventraDatabase" not in d:
    raise RuntimeError("Could not inject database into repository provider")
dbmodule.write_text(d)

print("Customization completed: atomic stock/sale writes, validation, Arabic RTL locale, app name and core Arabic labels.")
