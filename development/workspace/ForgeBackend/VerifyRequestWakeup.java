import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Real filesystem notifications; no game rules or timing options are changed. */
public final class VerifyRequestWakeup {
    static int checks;
    static void check(boolean value){if(!value)throw new AssertionError("Check "+(checks+1));checks++;}
    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);Files.createDirectory(root);
        try(var wake=new ForgeLandEngine.RequestWakeup(root)) {
            check(wake.watcher!=null);
            long start=System.nanoTime();wake.await(35);check(System.nanoTime()-start>=25_000_000);
            ExecutorService pool=Executors.newSingleThreadExecutor();
            try {
                var ready=new CountDownLatch(1);
                Future<?> waiting=pool.submit(()->{ready.countDown();try{wake.await(5000);}catch(InterruptedException ex){throw new RuntimeException(ex);}});
                check(ready.await(1,TimeUnit.SECONDS));
                Path pending=root.resolve("action.tmp");Files.writeString(pending,"{}");Files.move(pending,root.resolve("action.json"));
                waiting.get(2,TimeUnit.SECONDS);check(Files.readString(root.resolve("action.json")).equals("{}"));
                for(int i=0;i<100;i++)Files.writeString(root.resolve("storm-"+i+".json"),"{}");
                wake.await(1000);try(var paths=Files.list(root)){check(paths.filter(p->p.toString().endsWith(".json")).count()==101);}
                wake.close();wake.close();check(wake.watcher==null);wake.await(1);check(true);
            } finally {pool.shutdownNow();check(pool.awaitTermination(2,TimeUnit.SECONDS));}
        }
        // ZIP filesystems do not implement notifications; retain the old timed wait.
        try(var zip=FileSystems.newFileSystem(root.resolve("no-watch.zip"),Map.of("create","true"));var wake=new ForgeLandEngine.RequestWakeup(zip.getPath("/"))) {
            check(wake.watcher==null);wake.await(1);check(true);
        }
        System.out.println("Request wakeup: "+checks+" checks passed");
    }
}
