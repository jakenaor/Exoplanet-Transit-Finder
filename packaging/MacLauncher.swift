import AppKit
import Foundation

//MARK: the tiny window that owns the server thingy
final class Launcher: NSObject, NSApplicationDelegate
{
    var Window: NSWindow!
    var Status = NSTextField(wrappingLabelWithString: "starting the local server…")
    var OpenButton: NSButton!
    var Server: Process?
    var OutputPipe: Pipe?
    var Log: FileHandle?
    var LogURL: URL?
    var BrowserURL: URL?
    var PartialLine = ""
    var Quitting = false
    var StopSignal: DispatchSourceSignal?
    let Files = FileManager.default

    func applicationDidFinishLaunching(_ Notification: Notification)
    {
        // a normal terminate signal should use the same cleanup as the quit button.
        Darwin.signal(SIGTERM, SIG_IGN)
        StopSignal = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
        StopSignal?.setEventHandler { [weak self] in self?.QuitApp() }
        StopSignal?.resume()
        MakeWindow()
        StartServer()
    }

    func MakeWindow()
    {
        Window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 520, height: 250),
                          styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        Window.title = "Exoplanet Transit Finder"
        Window.center()
        let Heading = NSTextField(labelWithString: "Exoplanet Transit Finder")
        Heading.font = .boldSystemFont(ofSize: 23)
        Heading.frame = NSRect(x: 24, y: 192, width: 472, height: 32)
        Window.contentView!.addSubview(Heading)
        Status.frame = NSRect(x: 24, y: 112, width: 472, height: 68)
        Status.font = .systemFont(ofSize: 13)
        Window.contentView!.addSubview(Status)
        OpenButton = Button("Open in browser", #selector(OpenBrowser), 24, 74, 155)
        OpenButton.isEnabled = false
        _ = Button("Open sample files", #selector(OpenSamples), 193, 74, 155)
        _ = Button("Open log", #selector(OpenLog), 24, 24, 120)
        _ = Button("Quit", #selector(QuitApp), 376, 24, 120)
        let MenuBar = NSMenu()
        let AppItem = NSMenuItem()
        MenuBar.addItem(AppItem)
        let AppMenu = NSMenu()
        AppMenu.addItem(withTitle: "Quit Transit Finder", action: #selector(QuitApp), keyEquivalent: "q").target = self
        AppItem.submenu = AppMenu
        NSApp.mainMenu = MenuBar
        Window.makeKeyAndOrderFront(nil)
        if ProcessInfo.processInfo.environment["TRANSIT_FINDER_LAUNCHER_NO_BROWSER"] != "1"
        {
            NSApp.activate(ignoringOtherApps: true)
        }
    }

    func Button(_ Title: String, _ Action: Selector, _ X: CGFloat, _ Y: CGFloat, _ Width: CGFloat) -> NSButton
    {
        let Thing = NSButton(title: Title, target: self, action: Action)
        Thing.bezelStyle = .rounded
        Thing.frame = NSRect(x: X, y: Y, width: Width, height: 32)
        Window.contentView!.addSubview(Thing)
        return Thing
    }

    //MARK: stdout tells us which localhost port was free
    func StartServer()
    {
        do
        {
            let Support = Files.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
                .appendingPathComponent("Exoplanet Transit Finder", isDirectory: true)
            let Working = ProcessInfo.processInfo.environment["TRANSIT_FINDER_LAUNCHER_DATA_DIR"]
                .map { URL(fileURLWithPath: $0, isDirectory: true) } ?? Support
            try Files.createDirectory(at: Working, withIntermediateDirectories: true)
            LogURL = Working.appendingPathComponent("launcher.log")
            Files.createFile(atPath: LogURL!.path, contents: nil)
            Log = try FileHandle(forWritingTo: LogURL!)
            let Task = Process()
            Task.executableURL = Bundle.main.resourceURL!.appendingPathComponent("Server/TransitFinderServer")
            Task.currentDirectoryURL = Working
            var Environment = ProcessInfo.processInfo.environment
            for Key in ["PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"]
            {
                Environment.removeValue(forKey: Key)
            }
            Environment["TRANSIT_FINDER_NO_BROWSER"] = "1"
            Environment["TRANSIT_FINDER_SESSION_CACHE_DIR"] = Working.appendingPathComponent("Sessions").path
            Environment["TRANSIT_FINDER_CACHE_DIR"] = Working.appendingPathComponent("Cache").path
            Task.environment = Environment
            let PipeThing = Pipe()
            OutputPipe = PipeThing
            Task.standardOutput = PipeThing
            Task.standardError = PipeThing
            PipeThing.fileHandleForReading.readabilityHandler =
            {
                [weak self] Handle in
                let Data = Handle.availableData
                if Data.isEmpty
                {
                    Handle.readabilityHandler = nil
                    return
                }
                DispatchQueue.main.async
                {
                    self?.ReadOutput(Data)
                }
            }
            Task.terminationHandler =
            {
                [weak self] Finished in
                DispatchQueue.main.async
                {
                    guard let Owner = self, !Owner.Quitting else { return }
                    Owner.OpenButton.isEnabled = false
                    Owner.Status.stringValue = "server stopped (code \(Finished.terminationStatus)). open the log for details."
                }
            }
            Server = Task
            try Task.run()
        }
        catch
        {
            Status.stringValue = "could not start: \(error.localizedDescription)"
        }
    }

    func ReadOutput(_ Data: Data)
    {
        try? Log?.write(contentsOf: Data)
        PartialLine += String(decoding: Data, as: UTF8.self)
        while let End = PartialLine.firstIndex(of: "\n")
        {
            let Line = String(PartialLine[..<End])
            PartialLine.removeSubrange(...End)
            let Prefix = "Transit Finder running at "
            if Line.hasPrefix(Prefix), let URLThing = URL(string: String(Line.dropFirst(Prefix.count)))
            {
                BrowserURL = URLThing
                Status.stringValue = "running at \(URLThing.absoluteString)\nkeep this window open while using the app. Quit stops the server."
                OpenButton.isEnabled = true
                if ProcessInfo.processInfo.environment["TRANSIT_FINDER_LAUNCHER_NO_BROWSER"] != "1"
                {
                    OpenBrowser()
                }
            }
        }
    }

    //MARK: the buttons
    @objc func OpenBrowser()
    {
        if let URLThing = BrowserURL
        {
            NSWorkspace.shared.open(URLThing)
        }
    }

    @objc func OpenSamples()
    {
        NSWorkspace.shared.open(Bundle.main.resourceURL!.appendingPathComponent("Samples"))
    }

    @objc func OpenLog()
    {
        if let URLThing = LogURL
        {
            NSWorkspace.shared.open(URLThing)
        }
    }

    @objc func QuitApp()
    {
        NSApp.terminate(nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ Sender: NSApplication) -> Bool
    {
        return true
    }

    func applicationWillTerminate(_ Notification: Notification)
    {
        Quitting = true
        if let Task = Server, Task.isRunning
        {
            // don't leave a pile of tls workers behind when the app closes.
            Task.interrupt()
            Task.waitUntilExit()
        }
        OutputPipe?.fileHandleForReading.readabilityHandler = nil
        try? Log?.close()
    }
}

let App = NSApplication.shared
let AppDelegate = Launcher()
App.delegate = AppDelegate
App.setActivationPolicy(.regular)
App.run()
