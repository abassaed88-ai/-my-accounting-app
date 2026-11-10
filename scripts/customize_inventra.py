from pathlib import Path

root = Path("inventra/app/src/main/java/com/inventra/app")
repo = root / "data/repository/InventraRepository.kt"
s = repo.read_text()
s = s.replace("import com.inventra.app.data.local.dao.CategoryDao", "import androidx.room.withTransaction\nimport com.inventra.app.data.local.InventraDatabase\nimport com.inventra.app.data.local.dao.CategoryDao")
s = s.replace("    private val saleDao: SaleDao\n)", "    private val saleDao: SaleDao,\n    private val database: InventraDatabase\n)")
start = s.index("    suspend fun addStockPurchase(purchase: StockPurchaseEntity) {")
end = s.index("\n    fun computeNewAvgCost", start)
s = s[:start] + """    suspend fun addStockPurchase(purchase: StockPurchaseEntity): Result<Unit> {
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
""" + s[end:]
start = s.index("    suspend fun addSale(")
end = s.index("\n    suspend fun deleteSale", start)
s = s[:start] + """    suspend fun addSale(
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
""" + s[end:]
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
s = sales.read_text().replace('''            if (quantity <= 0) { _result.value = AddSaleResult.Error("Quantity must be > 0"); return@launch }
            if (sellingPrice < 0) { _result.value = AddSaleResult.Error("Selling price cannot be negative"); return@launch }''', '''            if (!quantity.isFinite() || quantity <= 0) { _result.value = AddSaleResult.Error("الكمية يجب أن تكون أكبر من صفر"); return@launch }
            if (!sellingPrice.isFinite() || sellingPrice < 0) { _result.value = AddSaleResult.Error("سعر البيع غير صالح"); return@launch }''')
sales.write_text(sales)

# Arabic app identity and right-to-left support
strings = Path("inventra/app/src/main/res/values/strings.xml")
if strings.exists():
    t = strings.read_text()
    import re
    t = re.sub(r'(<string name="app_name">).*?(</string>)', r'\1محاسبة متجري\2', t)
    strings.write_text(t)

activity = root / "MainActivity.kt"
t = activity.read_text()
if "Locale.setDefault" not in t:
    t = t.replace("import android.os.Bundle", "import android.os.Bundle\nimport java.util.Locale")
    t = t.replace("        super.onCreate(savedInstanceState)", "        super.onCreate(savedInstanceState)\n        Locale.setDefault(Locale("ar"))")
    activity.write_text(t)

print("Applied: atomic stock/sale updates, repository-level validation, error propagation, Arabic app name and Arabic locale.")
