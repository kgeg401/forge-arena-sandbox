import java.io.*;
import java.net.*;
import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import com.google.gson.*;
import forge.GuiDesktop;
import forge.gui.GuiBase;
import forge.model.FModel;

/** One database, sequential fresh games and fresh bridge static state per case.
 * This service is research-only. It cannot run imported decks or native clients.
 */
public final class ResearchGameWorker {
    static final Gson JSON=new GsonBuilder().setPrettyPrinting().create();
    static void write(Path path,Object data)throws Exception{
        Path pending=path.resolveSibling(path.getFileName()+".pending");
        Files.writeString(pending,JSON.toJson(data));
        Files.move(pending,path,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
    }
    static JsonObject read(Path path)throws Exception{return JsonParser.parseString(Files.readString(path)).getAsJsonObject();}
    static long heap(){Runtime r=Runtime.getRuntime();return r.totalMemory()-r.freeMemory();}
    static Set<Long> threads(){Set<Long> ids=new HashSet<>();for(Thread t:Thread.getAllStackTraces().keySet())if(t.isAlive()&&!t.isDaemon())ids.add(t.getId());return ids;}
    static class BridgeLoader extends URLClassLoader {
        BridgeLoader(Path classes)throws Exception{super(new URL[]{classes.toUri().toURL()},ResearchGameWorker.class.getClassLoader());}
        @Override protected Class<?> loadClass(String name,boolean resolve)throws ClassNotFoundException{
            if(!name.equals("ForgeLandEngine") && !name.startsWith("ForgeLandEngine$"))return super.loadClass(name,resolve);
            synchronized(getClassLoadingLock(name)){
                Class<?> found=findLoadedClass(name);if(found==null)found=findClass(name);
                if(resolve)resolveClass(found);return found;
            }
        }
    }
    public static void main(String[] args){
        try{run(args);System.exit(0);}catch(Throwable error){error.printStackTrace();System.exit(1);}
    }
    static void run(String[] args)throws Exception{
        Path runtime=Path.of(args[0]).toRealPath(),root=Path.of(args[1]).toRealPath(),classes=Path.of(args[2]).toRealPath();
        int maximum=Integer.parseInt(args[3]);if(maximum<1 || maximum>200)throw new IllegalArgumentException("Worker case bound 1..200");
        JsonObject manifest=read(runtime.getParent().resolve("native-lab/bridge-card-manifest.json"));
        if(!manifest.has("researchOnly") || !manifest.get("researchOnly").getAsBoolean() || Files.exists(runtime.getParent().resolve("native-lab/MTGA.exe")))throw new IllegalArgumentException("Only an independent research runtime is allowed");
        Files.createDirectories(root.resolve("jobs"));
        GuiBase.setInterface(new GuiDesktop(){@Override public String getAssetsDir(){return runtime.toString()+File.separator;}});
        long start=System.nanoTime();FModel.initialize(null,null);
        String worker=UUID.randomUUID().toString();
        write(root.resolve("ready.json"),Map.of("schema",1,"worker",worker,"pid",ProcessHandle.current().pid(),"initializationSeconds",(System.nanoTime()-start)/1e9,"researchOnly",true));
        int count=0;
        while(!Files.exists(root.resolve("stop.request")) && count<maximum){
            Path request=root.resolve("job.request.json");
            if(!Files.exists(request)){Thread.sleep(20);continue;}
            JsonObject job=read(request);String id=job.get("id").getAsString();
            if(!id.matches("[a-f0-9]{32}") || !worker.equals(job.get("worker").getAsString()))throw new IllegalArgumentException("Foreign or invalid worker job");
            Path ipc=root.resolve("jobs").resolve(id).toRealPath();
            if(!ipc.getParent().equals(root.resolve("jobs").toRealPath()) || Files.exists(ipc.resolve("completed.json")))throw new IllegalArgumentException("Job is outside this worker or already completed");
            JsonObject fixture=read(ipc.resolve("scenario.json"));
            if(!fixture.get("scenario").getAsString().equals("card-family"))throw new IllegalArgumentException("Warm worker only accepts card-family cases");
            Files.delete(request);
            long before=System.nanoTime();Set<Long> priorThreads=threads();Map<String,Object> result=new LinkedHashMap<>();
            result.put("schema",1);result.put("id",id);result.put("worker",worker);result.put("ordinal",++count);
            boolean failed=false;
            PrintStream stdout=System.out,stderr=System.err;
            ClassLoader previous=Thread.currentThread().getContextClassLoader();
            try(PrintStream capture=new PrintStream(Files.newOutputStream(ipc.resolve("engine.log")),true,"UTF-8");BridgeLoader loader=new BridgeLoader(classes)){
                System.setOut(capture);System.setErr(capture);Thread.currentThread().setContextClassLoader(loader);
                try{
                    Class<?> engine=Class.forName("ForgeLandEngine",true,loader);
                    if(engine.getClassLoader()!=loader)throw new IllegalStateException("Bridge static state was not isolated");
                    engine.getMethod("runResearchCase",String[].class).invoke(null,(Object)new String[]{runtime.toString(),ipc.toString()});
                    result.put("status","completed");
                    JsonObject state=read(ipc.resolve("state.json"));result.put("session",state.get("session").getAsString());
                    if(state.has("fidelityGap") && !state.get("fidelityGap").isJsonNull() && !state.get("fidelityGap").getAsString().isEmpty()){
                        result.put("fidelityGap",state.get("fidelityGap").getAsString());failed=true;
                    }
                }catch(Throwable error){
                    Throwable actual=error instanceof InvocationTargetException?((InvocationTargetException)error).getCause():error;
                    actual.printStackTrace();result.put("status","failed");result.put("error",actual.toString());failed=true;
                }finally{System.setOut(stdout);System.setErr(stderr);Thread.currentThread().setContextClassLoader(previous);}
            }
            Set<Long> added=threads();added.removeAll(priorThreads);
            result.put("newNonDaemonThreads",added);result.put("seconds",(System.nanoTime()-before)/1e9);result.put("heapBytesBeforeGc",heap());
            if(count%5==0){System.gc();Thread.sleep(50);}
            result.put("heapBytes",heap());
            boolean retire=failed || !added.isEmpty() || count>=maximum || heap()>768L*1024*1024;
            result.put("reusable",!retire);write(ipc.resolve("completed.json"),result);
            System.out.println(JSON.toJson(result));
            if(retire)break;
        }
        write(root.resolve("stopped.json"),Map.of("worker",worker,"cases",count,"heapBytes",heap()));
    }
}
