import * as vscode from 'vscode';
import { CodeRabbitAPI } from './api/coderabbit-api';
import { AnalysisProvider } from './providers/analysis-provider';
import { RealtimeAnalyzer } from './analyzers/realtime-analyzer';
import { StatusBarController } from './ui/status-bar';
import { ConfigurationManager } from './utils/configuration';
import { Logger } from './utils/logger';

export function activate(context: vscode.ExtensionContext) {
    const logger = new Logger('CodeRabbit Extension');
    logger.info('Activating CodeRabbit AI PR Reviewer extension...');

    try {
        // Initialize configuration
        const config = new ConfigurationManager();
        
        // Initialize API client
        const api = new CodeRabbitAPI(
            config.getApiEndpoint(),
            config.getApiKey()
        );

        // Initialize core components
        const analysisProvider = new AnalysisProvider(api, config);
        const realtimeAnalyzer = new RealtimeAnalyzer(api, config);
        const statusBar = new StatusBarController();

        // Register commands
        const commands = [
            vscode.commands.registerCommand('extension.coderabbit.analyzeCode', () => 
                analysisProvider.analyzeCurrentFile()
            ),
            vscode.commands.registerCommand('extension.coderabbit.analyzePR', () => 
                analysisProvider.analyzePullRequest()
            ),
            vscode.commands.registerCommand('extension.coderabbit.startRealtimeAnalysis', () => 
                realtimeAnalyzer.start()
            ),
            vscode.commands.registerCommand('extension.coderabbit.stopRealtimeAnalysis', () => 
                realtimeAnalyzer.stop()
            ),
            vscode.commands.registerCommand('extension.coderabbit.viewReport', () => 
                analysisProvider.showLatestReport()
            ),
            vscode.commands.registerCommand('extension.coderabbit.configureSettings', () => 
                vscode.commands.executeCommand('workbench.action.openSettings', '@ext:coderabbit.coderabbit-ai-pr-reviewer')
            )
        ];

        // Register event handlers
        const disposables = [
            ...commands,
            
            // File change events for real-time analysis
            vscode.workspace.onDidSaveTextDocument((document) => {
                if (config.isRealTimeEnabled() && config.shouldAnalyzeLanguage(document.languageId)) {
                    realtimeAnalyzer.analyzeDocument(document);
                }
            }),
            
            // Editor selection changes
            vscode.window.onDidChangeTextEditorSelection((event) => {
                if (config.isRealTimeEnabled() && event.textEditor?.document) {
                    realtimeAnalyzer.analyzeSelection(event.textEditor.document, event.textEditor.selection);
                }
            }),
            
            // Configuration changes
            vscode.workspace.onDidChangeConfiguration((event) => {
                if (event.affectsConfiguration('coderabbit')) {
                    config.reload();
                    logger.info('Configuration reloaded');
                }
            }),
            
            // View provider
            vscode.window.registerTreeDataProvider('coderabbitView', analysisProvider.getTreeDataProvider())
        ];

        // Add to subscriptions
        context.subscriptions.push(...disposables);

        // Update status bar
        statusBar.updateStatus('Ready', 'coderabbit.status.ready');
        
        logger.info('CodeRabbit extension activated successfully');

        // Show welcome message
        vscode.window.showInformationMessage(
            'CodeRabbit AI PR Reviewer is now active! Use the CodeRabbit commands in the command palette.',
            'View Documentation',
            'Configure Settings'
        ).then(selection => {
            if (selection === 'View Documentation') {
                vscode.env.openExternal(vscode.Uri.parse('https://docs.coderabbit.ai'));
            } else if (selection === 'Configure Settings') {
                vscode.commands.executeCommand('workbench.action.openSettings', '@ext:coderabbit.coderabbit-ai-pr-reviewer');
            }
        });

    } catch (error) {
        logger.error('Failed to activate CodeRabbit extension', error);
        vscode.window.showErrorMessage('Failed to activate CodeRabbit extension. Please check your configuration.');
    }
}

export function deactivate() {
    Logger.info('Deactivating CodeRabbit extension...');
}
