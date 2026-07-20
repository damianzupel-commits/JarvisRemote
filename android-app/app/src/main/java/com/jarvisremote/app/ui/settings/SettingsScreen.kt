package com.jarvisremote.app.ui.settings

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings as AndroidSettings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.viewmodel.compose.viewModel
import com.jarvisremote.app.phone.AccessibilityUtils
import com.jarvisremote.app.phone.PhoneLinkService

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(onSaved: () -> Unit, viewModel: SettingsViewModel = viewModel()) {
    val settings by viewModel.settings.collectAsState()
    val testState by viewModel.testState.collectAsState()
    val phoneLinkStatus by viewModel.phoneLinkStatus.collectAsState()

    var url by rememberSaveable(settings.backendUrl) { mutableStateOf(settings.backendUrl) }
    var apiKey by rememberSaveable(settings.apiKey) { mutableStateOf(settings.apiKey) }
    var showApiKey by rememberSaveable { mutableStateOf(false) }

    val context = LocalContext.current
    var accessibilityEnabled by remember { mutableStateOf(AccessibilityUtils.isEnabled(context)) }
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                accessibilityEnabled = AccessibilityUtils.isEnabled(context)
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    val folderPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            context.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
            )
            viewModel.savePhoneFolderUri(uri.toString())
        }
    }
    val notificationPermissionLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { /* no-op */ }

    Scaffold(topBar = { TopAppBar(title = { Text("Configuración de Jarvis") }) }) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                "Conectate al backend a través de tu red de Tailscale. Poné la IP " +
                    "de Tailscale de tu PC (tailscale ip -4) y el puerto del backend.",
                style = MaterialTheme.typography.bodyMedium,
            )

            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                label = { Text("URL del backend") },
                placeholder = { Text("http://100.x.x.x:8000") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                modifier = Modifier.fillMaxWidth(),
            )

            OutlinedTextField(
                value = apiKey,
                onValueChange = { apiKey = it },
                label = { Text("API key") },
                singleLine = true,
                visualTransformation = if (showApiKey) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    IconButton(onClick = { showApiKey = !showApiKey }) {
                        Icon(
                            if (showApiKey) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                            contentDescription = if (showApiKey) "Ocultar API key" else "Mostrar API key",
                        )
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )

            when (val state = testState) {
                is ConnectionTestState.Testing -> Text(
                    "Probando conexión...",
                    style = MaterialTheme.typography.bodySmall,
                )
                is ConnectionTestState.Success -> Text(
                    "✓ Conectado correctamente",
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.bodySmall,
                )
                is ConnectionTestState.Failure -> Text(
                    state.message,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
                ConnectionTestState.Idle -> {}
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = { viewModel.testConnection(url, apiKey) },
                    enabled = url.isNotBlank() && apiKey.isNotBlank(),
                ) {
                    Text("Probar conexión")
                }
                Button(
                    onClick = { viewModel.save(url, apiKey, onSaved) },
                    enabled = url.isNotBlank() && apiKey.isNotBlank(),
                ) {
                    Text("Guardar")
                }
            }

            HorizontalDivider()
            Text("Control del celular", style = MaterialTheme.typography.titleMedium)
            Text(
                "Le da a Jarvis acceso al filesystem del celular (carpeta elegida acá abajo) y " +
                    "control de pantalla vía Accessibility Service (tocar, deslizar, escribir, leer " +
                    "cualquier app en pantalla). Habilitalo solo si entendés y aceptás ese riesgo.",
                style = MaterialTheme.typography.bodySmall,
            )

            Text(
                "Carpeta: " + if (settings.phoneFolderUri.isBlank()) {
                    "ninguna elegida"
                } else {
                    Uri.parse(settings.phoneFolderUri).lastPathSegment ?: settings.phoneFolderUri
                },
                style = MaterialTheme.typography.bodyMedium,
            )
            OutlinedButton(onClick = { folderPicker.launch(null) }) {
                Text("Elegir carpeta")
            }

            Text(
                "Accessibility Service: " + if (accessibilityEnabled) "habilitado" else "no habilitado",
                color = if (accessibilityEnabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium,
            )
            OutlinedButton(onClick = { context.startActivity(Intent(AndroidSettings.ACTION_ACCESSIBILITY_SETTINGS)) }) {
                Text("Abrir Ajustes de Accesibilidad")
            }

            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text("Conexión con Jarvis (control remoto)", style = MaterialTheme.typography.bodyMedium)
                Switch(
                    checked = settings.phoneLinkEnabled,
                    onCheckedChange = { enabled ->
                        if (enabled && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                            notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                        }
                        viewModel.setPhoneLinkEnabled(enabled)
                    },
                )
            }
            if (settings.phoneLinkEnabled) {
                Text(
                    "Estado: " + when (phoneLinkStatus) {
                        PhoneLinkService.ConnectionStatus.CONNECTED -> "conectado"
                        PhoneLinkService.ConnectionStatus.CONNECTING -> "conectando..."
                        PhoneLinkService.ConnectionStatus.DISCONNECTED -> "desconectado, reintentando..."
                    },
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}
