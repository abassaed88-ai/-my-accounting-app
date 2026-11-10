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
    '"Save Changes"':'"حفظ التعديلات"',
    '"Sales History"':'"سجل المبيعات"',
    '"No sales recorded yet"':'"لم تُسجّل أي مبيعات بعد"',
    '"Tap + to record your first sale"':'"اضغط + لتسجيل أول مبيع"',
    '"Only ${formatQty(product.currentStockQty)} ${product.unit}(s) left"':'"المتبقي: ${formatQty(product.currentStockQty)} ${product.unit}"',
    '"Revenue: ${formatCurrency(dayRevenue)}  ·  Profit: ${formatCurrency(dayProfit)}"':'"المبيعات: ${formatCurrency(dayRevenue)}  ·  الربح: ${formatCurrency(dayProfit)}"',
    '"Inventra"':'"محاسبة متجري"',
    '"Actions"':'"إجراءات"',
    '"Sales"':'"المبيعات"',
    '"Purchases"':'"المشتريات"',
    '"Expenses"':'"المصاريف"',
    '"Debts"':'"الديون"',
    '"Search"':'"بحث"',
    '"Cancel"':'"إلغاء"',
    '"Delete"':'"حذف"',
    '"Confirm"':'"تأكيد"',
    '"Save"':'"حفظ"',
    '"Back"':'"رجوع"',
    '"Settings"':'"الإعدادات"',
    '"All"':'"الكل"',
    '"Date"':'"التاريخ"',
    '"Cost"':'"التكلفة"',
    '"Price"':'"السعر"',
    '"Total"':'"الإجمالي"'
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



# Arabic-first colorful dashboard redesign.
dashboard = root / "presentation/dashboard/DashboardScreen.kt"
dashboard.write_text(r'''package com.inventra.app.presentation.dashboard

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddShoppingCart
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.inventra.app.domain.model.Product
import com.inventra.app.domain.model.Sale
import com.inventra.app.ui.components.formatCurrency
import com.inventra.app.ui.components.formatQty
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val Navy = Color(0xFF172554)
private val Blue = Color(0xFF2563EB)
private val Teal = Color(0xFF0F9D8A)
private val Purple = Color(0xFF7C3AED)
private val Orange = Color(0xFFEA8A22)
private val Pale = Color(0xFFF4F7FC)

@Composable
fun DashboardScreen(onAddSale: () -> Unit, onStockIn: () -> Unit, viewModel: DashboardViewModel = hiltViewModel()) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val recentSales by viewModel.recentSales.collectAsStateWithLifecycle()
    val lowStockProducts by viewModel.lowStockProducts.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { viewModel.loadTodaySummary() }
    val summary = uiState.todaySummary
    Scaffold(containerColor = Pale, floatingActionButton = {
        ExtendedFloatingActionButton(onClick = onAddSale, icon = { Icon(Icons.Default.AddShoppingCart, null) },
            text = { Text("تسجيل مبيع جديد", fontWeight = FontWeight.Bold) },
            containerColor = Blue, contentColor = Color.White)
    }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 14.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)) {
            item {
                Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(26.dp),
                    colors = CardDefaults.cardColors(containerColor = Navy)) {
                    Column(Modifier.fillMaxWidth().padding(20.dp)) {
                        Text("محاسبة متجري", color = Color.White, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold)
                        Spacer(Modifier.height(5.dp))
                        Text(SimpleDateFormat("EEEE، d MMMM yyyy", Locale("ar")).format(Date()),
                            color = Color.White.copy(alpha = .78f))
                        Spacer(Modifier.height(18.dp))
                        Text("إجمالي مبيعات اليوم", color = Color.White.copy(alpha = .85f))
                        Text(formatCurrency(summary.totalRevenue), color = Color.White,
                            style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
                    }
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    MetricCard("صافي الربح", formatCurrency(summary.totalProfit), Teal, Modifier.weight(1f))
                    MetricCard("القطع المباعة", formatQty(summary.totalUnitsSold), Purple, Modifier.weight(1f))
                }
            }
            item {
                Text("الوصول السريع", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = Navy)
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                    QuickAction("تسجيل مبيع", "أدخل عملية بيع", Blue, Icons.Default.AddShoppingCart, onAddSale, Modifier.weight(1f))
                    QuickAction("إدخال بضاعة", "تحديث المخزون", Orange, Icons.Default.Inventory2, onStockIn, Modifier.weight(1f))
                }
            }
            if (lowStockProducts.isNotEmpty()) {
                item { Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.WarningAmber, null, tint = Orange)
                    Spacer(Modifier.width(7.dp))
                    Text("تنبيهات المخزون", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = Navy)
                } }
                items(lowStockProducts) { LowStockCard(it) }
            }
            item { Text("آخر المبيعات", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = Navy) }
            if (recentSales.isEmpty()) {
                item {
                    Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(18.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                        Column(Modifier.fillMaxWidth().padding(22.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(Icons.Default.TrendingUp, null, tint = Blue, modifier = Modifier.size(34.dp))
                            Spacer(Modifier.height(8.dp))
                            Text("لا توجد مبيعات مسجلة بعد", fontWeight = FontWeight.Bold, color = Navy)
                            Text("ابدأ بتسجيل أول عملية بيع من الزر بالأسفل", color = Color.Gray, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            } else { items(recentSales) { SaleCard(it) } }
        }
    }
}

@Composable
private fun MetricCard(title: String, value: String, color: Color, modifier: Modifier = Modifier) {
    Card(modifier, shape = RoundedCornerShape(20.dp), colors = CardDefaults.cardColors(containerColor = color)) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            Text(title, color = Color.White.copy(alpha = .88f))
            Spacer(Modifier.height(8.dp))
            Text(value, color = Color.White, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
        }
    }
}

@Composable
private fun QuickAction(title: String, subtitle: String, color: Color, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Card(onClick = onClick, modifier = modifier, shape = RoundedCornerShape(20.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Column(Modifier.fillMaxWidth().padding(14.dp)) {
            Box(Modifier.size(42.dp).background(color.copy(alpha = .12f), RoundedCornerShape(14.dp)), contentAlignment = Alignment.Center) {
                Icon(icon, null, tint = color)
            }
            Spacer(Modifier.height(10.dp))
            Text(title, color = Navy, fontWeight = FontWeight.Bold)
            Text(subtitle, color = Color.Gray, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun LowStockCard(product: Product) {
    Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF5E8))) {
        Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.WarningAmber, null, tint = Orange)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(product.name, fontWeight = FontWeight.Bold, color = Navy)
                Text("المتبقي: ${formatQty(product.currentStockQty)} ${product.unit}", color = Color.DarkGray, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun SaleCard(sale: Sale) {
    Card(Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(sale.productName, color = Navy, fontWeight = FontWeight.Bold)
                Text("${formatQty(sale.quantity)} × ${formatCurrency(sale.sellingPricePerUnit)}", color = Color.Gray, style = MaterialTheme.typography.bodySmall)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(formatCurrency(sale.totalRevenue), color = Navy, fontWeight = FontWeight.Bold)
                Text("ربح ${formatCurrency(sale.profit)}", color = if (sale.profit >= 0) Teal else Color.Red, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
''')



# Manual USD/SYP exchange rate and dual-currency display.
currency_dir = root / "presentation/currency"
currency_dir.mkdir(parents=True, exist_ok=True)
(currency_dir / "CurrencyUi.kt").write_text(r'''package com.inventra.app.presentation.currency

import android.content.Context
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CurrencyExchange
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import java.text.DecimalFormat
import java.text.DecimalFormatSymbols
import java.util.Locale

object CurrencyPrefs {
    private const val PREFS = "accounting_currency_settings"
    private const val KEY_RATE = "usd_to_syp_rate"
    val rateState = mutableStateOf(0.0)
    fun load(context: Context) {
        rateState.value = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_RATE, "0")?.toDoubleOrNull() ?: 0.0
    }
    fun save(context: Context, rate: Double) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_RATE, rate.toString()).apply()
        rateState.value = rate
    }
    fun getRate(): Double = rateState.value
}

@Composable
fun dualCurrencyLabel(amountUsd: Double): String {
    val context = LocalContext.current
    LaunchedEffect(Unit) { CurrencyPrefs.load(context) }
    val rate by CurrencyPrefs.rateState
    val usd = "$" + DecimalFormat("#,##0.##").format(amountUsd)
    return if (rate > 0.0) {
        val syp = DecimalFormat("#,##0", DecimalFormatSymbols(Locale("ar"))).format(amountUsd * rate)
        "$usd  |  $syp ل.س"
    } else "$usd  |  حدّد سعر الصرف"
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CurrencySettingsScreen() {
    val context = LocalContext.current
    val rate by CurrencyPrefs.rateState
    var input by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        CurrencyPrefs.load(context)
        if (CurrencyPrefs.getRate() > 0.0) input = CurrencyPrefs.getRate().toString()
    }
    Scaffold(
        containerColor = Color(0xFFF4F7FC),
        topBar = { TopAppBar(title = { Text("إعدادات العملات", fontWeight = FontWeight.Bold) }) }
    ) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(18.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Card(shape = RoundedCornerShape(22.dp), colors = CardDefaults.cardColors(containerColor = Color(0xFF172554))) {
                Column(Modifier.fillMaxWidth().padding(20.dp)) {
                    Icon(Icons.Default.CurrencyExchange, null, tint = Color.White, modifier = Modifier.size(32.dp))
                    Spacer(Modifier.height(10.dp))
                    Text("الليرة السورية والدولار", color = Color.White, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text("سيظهر كل مبلغ بالعملتين جنباً إلى جنب وفق السعر الذي تحدده.", color = Color.White.copy(alpha = .8f))
                }
            }
            Text("سعر صرف الدولار", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = input, onValueChange = { input = it; message = null },
                modifier = Modifier.fillMaxWidth(), label = { Text("كم ليرة سورية تساوي 1 دولار؟") },
                placeholder = { Text("مثال: 13000") }, suffix = { Text("ل.س / $1") },
                singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal)
            )
            Button(onClick = {
                val value = input.trim().replace(",", ".").toDoubleOrNull()
                if (value == null || !value.isFinite() || value <= 0.0) message = "أدخل سعر صرف صحيحاً أكبر من صفر"
                else { CurrencyPrefs.save(context, value); message = "تم حفظ سعر الصرف على هذا الجهاز" }
            }, modifier = Modifier.fillMaxWidth().height(52.dp)) { Text("حفظ سعر الصرف", fontWeight = FontWeight.Bold) }
            if (message != null) Text(message!!, color = if (rate > 0.0) Color(0xFF087F5B) else MaterialTheme.colorScheme.error)
            Card(shape = RoundedCornerShape(18.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
                Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("السعر المعتمد حالياً", fontWeight = FontWeight.Bold)
                    if (rate > 0.0) {
                        Text("1 دولار = ${DecimalFormat("#,##0.##").format(rate)} ليرة سورية", style = MaterialTheme.typography.titleMedium, color = Color(0xFF2563EB), fontWeight = FontWeight.Bold)
                        Text("يمكنك تغييره في أي وقت، وسيُستخدم في عرض القيم المحوّلة.", color = Color.Gray, style = MaterialTheme.typography.bodySmall)
                    } else Text("لم يتم تحديد سعر صرف بعد", color = Color(0xFFB45309))
                }
            }
            Text("الأسعار الأصلية والعمليات المحاسبية تبقى محفوظة بقيمتها الأساسية بالدولار، ويُعرض مقابلها بالليرة حسب السعر الذي تحدده. تغيير السعر لا يغيّر سجلات المبيعات أو الأرباح السابقة.", color = Color.Gray, style = MaterialTheme.typography.bodySmall)
        }
    }
}
''')

dashboard = root / "presentation/dashboard/DashboardScreen.kt"
d = dashboard.read_text()
d = d.replace("import com.inventra.app.ui.components.formatCurrency", "import com.inventra.app.ui.components.formatCurrency\nimport com.inventra.app.presentation.currency.dualCurrencyLabel")
d = d.replace("formatCurrency(summary.totalRevenue)", "dualCurrencyLabel(summary.totalRevenue)")
d = d.replace("formatCurrency(summary.totalProfit)", "dualCurrencyLabel(summary.totalProfit)")
d = d.replace("formatCurrency(sale.totalRevenue)", "dualCurrencyLabel(sale.totalRevenue)")
d = d.replace("formatCurrency(sale.profit)", "dualCurrencyLabel(sale.profit)")
dashboard.write_text(d)

# Apply the selected USD/SYP display consistently to analytics totals and product rankings.
analytics = root / "presentation/analytics/AnalyticsScreen.kt"
a = analytics.read_text()
if "import com.inventra.app.presentation.currency.dualCurrencyLabel" not in a:
    a = a.replace("import com.inventra.app.ui.components.formatCurrency",
                  "import com.inventra.app.ui.components.formatCurrency\nimport com.inventra.app.presentation.currency.dualCurrencyLabel")
for old, new in [
    ("formatCurrency(summary.totalRevenue)", "dualCurrencyLabel(summary.totalRevenue)"),
    ("formatCurrency(summary.totalProfit)", "dualCurrencyLabel(summary.totalProfit)"),
    ("formatCurrency(summary.totalCost)", "dualCurrencyLabel(summary.totalCost)"),
    ("formatCurrency(p.totalRevenue)", "dualCurrencyLabel(p.totalRevenue)"),
    ("formatCurrency(p.totalProfit)", "dualCurrencyLabel(p.totalProfit)"),
    ("formatCurrency(state.summary.totalRevenue)", "dualCurrencyLabel(state.summary.totalRevenue)"),
    ("formatCurrency(state.summary.totalProfit)", "dualCurrencyLabel(state.summary.totalProfit)")
]:
    a = a.replace(old, new)
analytics.write_text(a)

nav = root / "presentation/navigation/NavGraph.kt"
n = nav.read_text()
n = n.replace("import androidx.compose.material.icons.filled.ShoppingBag", "import androidx.compose.material.icons.filled.ShoppingBag\nimport androidx.compose.material.icons.filled.Settings")
n = n.replace("import androidx.compose.material.icons.outlined.ShoppingBag", "import androidx.compose.material.icons.outlined.ShoppingBag\nimport androidx.compose.material.icons.outlined.Settings")
n = n.replace("import com.inventra.app.presentation.stock.StockInScreen", "import com.inventra.app.presentation.stock.StockInScreen\nimport com.inventra.app.presentation.currency.CurrencySettingsScreen")
n = n.replace('    object Inventory : Screen("inventory")', '    object Inventory : Screen("inventory")\n    object Currency : Screen("currency")')
n = n.replace('    BottomNavItem(Screen.Inventory, "Inventory", Icons.Filled.Inventory, Icons.Outlined.Inventory),', '    BottomNavItem(Screen.Inventory, "Inventory", Icons.Filled.Inventory, Icons.Outlined.Inventory),\n    BottomNavItem(Screen.Currency, "العملات", Icons.Filled.Settings, Icons.Outlined.Settings),')
n = n.replace('            composable(Screen.Inventory.route) { InventoryScreen() }', '            composable(Screen.Inventory.route) { InventoryScreen() }\n            composable(Screen.Currency.route) { CurrencySettingsScreen() }')
nav.write_text(n)

print("Customization completed: Arabic colorful dashboard, manual USD/SYP exchange rate, dual currency display and Arabic RTL.")

print("Customization completed: atomic stock/sale writes, validation, Arabic RTL locale, app branding and expanded Arabic labels.")


# Invoices are generated from existing sales records; they never create duplicate sales.
invoice_dir = root / "presentation/invoices"
invoice_dir.mkdir(parents=True, exist_ok=True)

(invoice_dir / "InvoiceViewModel.kt").write_text(r'''package com.inventra.app.presentation.invoices

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.inventra.app.data.repository.InventraRepository
import com.inventra.app.domain.model.Sale
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

@HiltViewModel
class InvoiceViewModel @Inject constructor(repository: InventraRepository) : ViewModel() {
    val sales: StateFlow<List<Sale>> = repository.getRecentSales(200)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
}
''')

(invoice_dir / "InvoiceScreen.kt").write_text(r'''package com.inventra.app.presentation.invoices

import android.content.Intent
import android.graphics.Paint
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import android.text.Layout
import android.text.StaticLayout
import android.text.TextDirectionHeuristics
import android.text.TextPaint
import android.widget.Toast
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.inventra.app.domain.model.Sale
import com.inventra.app.presentation.currency.dualCurrencyLabel
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InvoiceScreen(onBack: () -> Unit, viewModel: InvoiceViewModel = hiltViewModel()) {
    val context = LocalContext.current
    val sales by viewModel.sales.collectAsStateWithLifecycle()
    val selectedIds = remember { mutableStateListOf<String>() }
    var customer by remember { mutableStateOf("") }
    var invoiceNumber by remember { mutableStateOf("INV-" + System.currentTimeMillis().toString().takeLast(6)) }
    var notes by remember { mutableStateOf("") }
    var savedInvoices by remember { mutableStateOf(emptyList<File>()) }
    val date = remember { SimpleDateFormat("yyyy/MM/dd", Locale("ar")).format(Date()) }
    val selected = sales.filter { selectedIds.contains(it.id) }
    val total = selected.sumOf { it.totalRevenue }
    val totalLabel = dualCurrencyLabel(total)

    LaunchedEffect(Unit) {
        val folder = File(context.filesDir, "invoices")
        savedInvoices = folder.listFiles()?.filter { it.extension.equals("pdf", true) }?.sortedByDescending { it.lastModified() } ?: emptyList()
    }

    fun invoiceText(): String {
        val out = StringBuilder()
        out.append("فاتورة مبيعات\nرقم الفاتورة: ").append(invoiceNumber)
            .append("\nالتاريخ: ").append(date)
            .append("\nاسم العميل: ").append(customer.ifBlank { "—" })
            .append("\n================================\nالمواد المباعة:\n")
        selected.forEachIndexed { index, sale ->
            out.append(index + 1).append(") ").append(sale.productName)
                .append("\nالكمية: ").append(sale.quantity).append(" ").append(sale.productUnit)
                .append("\nسعر الوحدة: $").append(String.format(Locale.US, "%,.2f", sale.sellingPricePerUnit))
                .append("\nالإجمالي: $").append(String.format(Locale.US, "%,.2f", sale.totalRevenue))
                .append("\nرقم سجل المبيع: ").append(sale.id)
                .append("\n--------------------------------\n")
        }
        out.append("إجمالي الفاتورة: ").append(totalLabel)
        if (notes.isNotBlank()) out.append("\nملاحظات: ").append(notes)
        out.append("\nتم إنشاء الفاتورة من عمليات البيع المسجلة في المخزون.")
        return out.toString()
    }

    fun createPdf(): File {
        val content = invoiceText()
        val paint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.DKGRAY
            textSize = 16f
        }
        val layout = StaticLayout.Builder.obtain(content, 0, content.length, paint, 500)
            .setAlignment(Layout.Alignment.ALIGN_OPPOSITE)
            .setTextDirection(TextDirectionHeuristics.RTL)
            .setLineSpacing(7f, 1f).build()
        val doc = PdfDocument()
        val pageHeight = 842
        val top = 115f
        val usable = 680f
        val pages = maxOf(1, kotlin.math.ceil(layout.height / usable).toInt())
        repeat(pages) { index ->
            val page = doc.startPage(PdfDocument.PageInfo.Builder(595, pageHeight, index + 1).create())
            val title = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = android.graphics.Color.rgb(23, 37, 84)
                textSize = 22f
                typeface = Typeface.create(Typeface.DEFAULT, Typeface.BOLD)
                textAlign = Paint.Align.RIGHT
            }
            page.canvas.drawText("فاتورة مبيعات - " + invoiceNumber, 540f, 70f, title)
            page.canvas.save()
            page.canvas.clipRect(35f, top, 560f, top + usable)
            page.canvas.translate(45f, top - index * usable)
            layout.draw(page.canvas)
            page.canvas.restore()
            doc.finishPage(page)
        }
        val folder = File(context.filesDir, "invoices").apply { mkdirs() }
        val file = File(folder, "invoice_" + System.currentTimeMillis() + ".pdf")
        file.outputStream().use { doc.writeTo(it) }
        doc.close()
        return file
    }

    fun sharePdf(file: File) {
        try {
            val uri = FileProvider.getUriForFile(context, context.packageName + ".fileprovider", file)
            val send = Intent(Intent.ACTION_SEND).apply {
                type = "application/pdf"
                putExtra(Intent.EXTRA_STREAM, uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            context.startActivity(Intent.createChooser(send, "إرسال الفاتورة"))
        } catch (e: Exception) {
            Toast.makeText(context, "تعذرت مشاركة الفاتورة: " + e.message, Toast.LENGTH_LONG).show()
        }
    }

    Scaffold(topBar = {
        TopAppBar(
            title = { Text("إنشاء فاتورة من المبيعات", fontWeight = FontWeight.Bold) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "رجوع") } }
        )
    }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
            OutlinedTextField(invoiceNumber, { invoiceNumber = it }, label = { Text("رقم الفاتورة") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            OutlinedTextField(customer, { customer = it }, label = { Text("اسم العميل") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
            Text("اختر عمليات البيع الفعلية:", fontWeight = FontWeight.Bold)
            if (sales.isEmpty()) {
                Text("لا توجد مبيعات مسجلة. سجّل مبيعاً أولاً ثم أنشئ الفاتورة.")
            } else {
                LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    items(sales, key = { it.id }) { sale ->
                        Card(onClick = {
                            if (selectedIds.contains(sale.id)) selectedIds.remove(sale.id) else selectedIds.add(sale.id)
                        }, shape = RoundedCornerShape(12.dp)) {
                            Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                                Checkbox(selectedIds.contains(sale.id), { checked ->
                                    if (checked && !selectedIds.contains(sale.id)) selectedIds.add(sale.id)
                                    if (!checked) selectedIds.remove(sale.id)
                                })
                                Column(Modifier.weight(1f)) {
                                    Text(sale.productName, fontWeight = FontWeight.Bold)
                                    Text(sale.quantity.toString() + " " + sale.productUnit + " × " + dualCurrencyLabel(sale.sellingPricePerUnit),
                                        style = MaterialTheme.typography.bodySmall)
                                    Text(SimpleDateFormat("yyyy/MM/dd HH:mm", Locale("ar")).format(Date(sale.date)),
                                        style = MaterialTheme.typography.labelSmall)
                                }
                                Text(dualCurrencyLabel(sale.totalRevenue), fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }
            OutlinedTextField(notes, { notes = it }, label = { Text("ملاحظات اختيارية") }, modifier = Modifier.fillMaxWidth())
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                Column(Modifier.fillMaxWidth().padding(12.dp)) {
                    Text("عمليات مختارة: " + selected.size)
                    Text("إجمالي الفاتورة: " + totalLabel, fontWeight = FontWeight.ExtraBold,
                        style = MaterialTheme.typography.titleLarge)
                    Text("التاريخ: " + date, style = MaterialTheme.typography.bodySmall)
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = {
                    val clipboard = context.getSystemService(android.content.Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager
                    clipboard.setPrimaryClip(android.content.ClipData.newPlainText("فاتورة", invoiceText()))
                    Toast.makeText(context, "تم نسخ الفاتورة", Toast.LENGTH_SHORT).show()
                }, enabled = selected.isNotEmpty(), modifier = Modifier.weight(1f)) { Text("نسخ النص") }
                Button(onClick = {
                    try {
                        val file = createPdf()
                        savedInvoices = listOf(file) + savedInvoices
                        sharePdf(file)
                    } catch (e: Exception) {
                        Toast.makeText(context, "تعذر إنشاء PDF: " + e.message, Toast.LENGTH_LONG).show()
                    }
                }, enabled = selected.isNotEmpty(), modifier = Modifier.weight(1f)) { Text("PDF ومشاركة") }
            }
            if (savedInvoices.isNotEmpty()) {
                Text("الفواتير المحفوظة", fontWeight = FontWeight.Bold)
                savedInvoices.take(3).forEach { file ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(file.nameWithoutExtension, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
                        TextButton(onClick = { sharePdf(file) }) { Text("مشاركة") }
                    }
                }
            }
        }
    }
}
''')

nav = root / "presentation/navigation/NavGraph.kt"
n = nav.read_text()
if "import com.inventra.app.presentation.invoices.InvoiceScreen" not in n:
    n = n.replace("import com.inventra.app.presentation.stock.StockInScreen",
                  "import com.inventra.app.presentation.stock.StockInScreen\nimport com.inventra.app.presentation.invoices.InvoiceScreen")
if 'object Invoices : Screen("invoices")' not in n:
    n = n.replace('    object Inventory : Screen("inventory")',
                  '    object Inventory : Screen("inventory")\n    object Invoices : Screen("invoices")')
if 'BottomNavItem(Screen.Invoices' not in n:
    n = n.replace('    BottomNavItem(Screen.Inventory, "Inventory", Icons.Filled.Inventory, Icons.Outlined.Inventory),',
                  '    BottomNavItem(Screen.Inventory, "Inventory", Icons.Filled.Inventory, Icons.Outlined.Inventory),\n    BottomNavItem(Screen.Invoices, "الفواتير", Icons.Filled.Description, Icons.Outlined.Description),')
if 'composable(Screen.Invoices.route)' not in n:
    n = n.replace('            composable(Screen.Inventory.route) { InventoryScreen() }',
                  '            composable(Screen.Inventory.route) { InventoryScreen() }\n            composable(Screen.Invoices.route) { InvoiceScreen(onBack = { navController.popBackStack() }) }')
n = n.replace("import androidx.compose.material.icons.filled.ShoppingBag",
              "import androidx.compose.material.icons.filled.ShoppingBag\nimport androidx.compose.material.icons.filled.Description")
n = n.replace("import androidx.compose.material.icons.outlined.ShoppingBag",
              "import androidx.compose.material.icons.outlined.ShoppingBag\nimport androidx.compose.material.icons.outlined.Description")
nav.write_text(n)

print("Invoices now select existing recorded sales, display real product/quantity/price values, calculate totals automatically and export/share multi-page PDF or copyable text. No duplicate sale or stock adjustment is created.")
